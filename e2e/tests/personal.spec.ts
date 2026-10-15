import { expect, test } from '@playwright/test';
import { resetDatabase } from '../db';
import { ADMIN, VENTAS } from '../env';
import {
  createApprovedClient,
  login,
  logout,
  PNG,
  seedEquipos,
  signIn,
  userHeaders,
} from './helpers';
import { linkFromMail } from './mail';
import { apartarPorApi, confirmarPorApi, equipoId } from './rentas-api';

const C = {
  email: 'obra@personal-e2e.com',
  password: 'cliente-obra-clave-1',
  rfc: 'PER010101AB1',
  razonSocial: 'Constructora Personal SA de CV',
};
const OPERADOR = {
  name: 'Operador Nuevo',
  email: 'operador@personal-e2e.com',
  password: 'operador-clave-123',
};

let renta = { id: '', folio: '' };

test.beforeAll(() => resetDatabase());

test.describe.serial('Personal y operador', () => {
  test('preparación: una renta confirmada', async ({ request }) => {
    await seedEquipos(request, 'Categoría Personal E2E', [
      { codigo: 'PER-A', nombre: 'Personal Alfa', horometro: 500 },
    ]);
    await createApprovedClient(request, C);
    const cliente = await userHeaders(request, C.email, C.password);
    const ventas = await userHeaders(request, VENTAS.email, VENTAS.password);
    renta = await apartarPorApi(
      request,
      cliente,
      ventas,
      await equipoId(request, cliente, 'PER-A'),
    );
    await confirmarPorApi(request, cliente, ventas, renta.id);
  });

  test('solo el administrador ve y usa la sección de personal', async ({ page }) => {
    await signIn(page, VENTAS.email, VENTAS.password);
    await expect(page.getByRole('link', { name: 'Personal' })).toHaveCount(0);
    await page.goto('/admin/personal');
    await expect(page).not.toHaveURL(/\/admin\/personal/);
    await logout(page);
  });

  test('el admin da de alta a un operador y este crea su contraseña', async ({ page, browser }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.getByRole('link', { name: 'Personal' }).click();
    await page.getByLabel('Nombre completo').fill(OPERADOR.name);
    await page.getByLabel('Correo').fill(OPERADOR.email);
    await page.getByLabel('Rol', { exact: true }).selectOption('operador');
    await page.getByRole('button', { name: 'Enviar invitación' }).click();

    const fila = page.locator(`[data-persona="${OPERADOR.email}"]`);
    await expect(fila).toContainText('Invitación pendiente');
    await expect(fila.getByRole('button', { name: 'Reenviar invitación' })).toBeVisible();
    // El admin no puede quitarse a sí mismo.
    const yo = page.locator(`[data-persona="${ADMIN.email}"]`);
    await expect(yo.getByRole('button', { name: 'Dar de baja' })).toHaveCount(0);

    const otra = await (await browser.newContext()).newPage();
    await otra.goto(await linkFromMail(OPERADOR.email, 'te dio acceso'));
    await otra.getByLabel(/Contraseña/).fill(OPERADOR.password);
    await otra.getByRole('button', { name: 'Guardar contraseña' }).click();
    await expect(otra.getByRole('status')).toContainText('Contraseña guardada');

    await page.reload();
    await expect(fila).toContainText('Activo');
    await logout(page);
  });

  test('el operador ve la entrega pendiente y registra la salida y el regreso', async ({
    page,
  }) => {
    await login(page, OPERADOR.email, OPERADOR.password);
    await expect(page).toHaveURL(/\/operador$/);
    await expect(page.getByRole('link', { name: 'Cobranza' })).toHaveCount(0);
    await expect(page.getByRole('list', { name: 'Por entregar' })).toContainText('Personal Alfa');

    await page.getByRole('link', { name: 'Entregar' }).click();
    await expect(page.getByRole('heading', { name: renta.folio })).toBeVisible();
    // No ve cotización, pagos ni documentos.
    await expect(page.getByRole('heading', { name: 'Cumplimiento y pagos' })).toHaveCount(0);
    await expect(page.getByTestId('pagado')).toHaveCount(0);

    await page.getByLabel('Horómetro (h)').fill('500');
    await page.getByLabel('Foto del tablero').setInputFiles(PNG);
    await page.getByRole('button', { name: 'Registrar salida' }).click();
    await expect(page.locator('app-status-badge').getByText('En renta')).toBeVisible();

    await page.getByLabel('Horómetro (h)').fill('507.5');
    await page.getByLabel('Foto del tablero').setInputFiles(PNG);
    await page.getByRole('button', { name: 'Registrar regreso' }).click();
    await expect(page.locator('app-status-badge').getByText('Devuelta')).toBeVisible();
    await expect(page.getByTestId('horas-usadas')).toContainText('7.5 h');
    await logout(page);
  });

  test('dar de baja a una persona le cierra la sesión y le impide entrar', async ({
    page,
    browser,
  }) => {
    const sesion = await (await browser.newContext()).newPage();
    await login(sesion, OPERADOR.email, OPERADOR.password);
    await expect(sesion).toHaveURL(/\/operador$/);

    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/personal');
    const fila = page.locator(`[data-persona="${OPERADOR.email}"]`);
    await fila.getByRole('button', { name: 'Dar de baja' }).click();
    await expect(fila).toContainText('De baja');

    await login(sesion, OPERADOR.email, OPERADOR.password);
    await expect(sesion.getByRole('alert')).toContainText('incorrectos');

    await fila.getByRole('button', { name: 'Reactivar' }).click();
    await expect(fila).toContainText('Activo');
    await logout(page);
  });
});
