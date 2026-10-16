import { expect, test } from '@playwright/test';
import { resetDatabase } from '../db';
import { ADMIN, VENTAS } from '../env';
import {
  adminHeaders,
  createApprovedClient,
  logout,
  seedEquipos,
  signIn,
  userHeaders,
} from './helpers';
import { apartarPorApi, confirmarPorApi, equipoId } from './rentas-api';

const C = {
  email: 'panel@panel-e2e.com',
  password: 'cliente-panel-clave-1',
  rfc: 'PAN010101AB1',
  razonSocial: 'Constructora Panel SA de CV',
};

let equipo = { id: '', codigo: 'PAN-A' };

test.beforeAll(() => resetDatabase());

test.describe.serial('Panel del administrador y gastos', () => {
  test('preparación: una renta confirmada con el anticipo cobrado', async ({ request }) => {
    [equipo.id] = await seedEquipos(request, 'Categoría Panel E2E', [
      { codigo: equipo.codigo, nombre: 'Panel Alfa' },
    ]);
    await createApprovedClient(request, C);
    const cliente = await userHeaders(request, C.email, C.password);
    const ventas = await userHeaders(request, VENTAS.email, VENTAS.password);
    const renta = await apartarPorApi(
      request,
      cliente,
      ventas,
      await equipoId(request, cliente, equipo.codigo),
    );
    await confirmarPorApi(request, cliente, ventas, renta.id);
  });

  test('el panel muestra lo cobrado, la ganancia y las gráficas', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await expect(page).toHaveURL(/\/admin$/);
    await expect(page.getByRole('heading', { name: /^Hola, / })).toBeVisible();

    await expect(page.getByTestId('ganancia')).toContainText('$3,480');
    await expect(page.getByText('Ganancia del mes')).toBeVisible();
    const ingresos = page.locator('app-kpi-card', { hasText: 'Ingresos cobrados' });
    await expect(ingresos).toContainText('$3,480');
    await expect(page.locator('app-kpi-card', { hasText: 'Por cobrar' })).toContainText('$8,120');
    await expect(page.locator('app-kpi-card', { hasText: 'Vendido' })).toContainText('$11,600');

    await expect(
      page.getByRole('img', { name: 'Ingresos, gastos y ganancia por mes' }),
    ).toBeVisible();
    await expect(page.getByLabel('Equipos con más ingresos')).toContainText('Panel Alfa');
    await expect(page.getByLabel('Próximas salidas')).toContainText('Panel Alfa');
    await logout(page);
  });

  test('un gasto mayor a lo cobrado convierte la ganancia en pérdida', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.getByRole('link', { name: 'Gastos', exact: true }).click();
    await page.getByLabel('Concepto').fill('Diésel y refacciones');
    await page.getByLabel('Categoría del gasto').selectOption('combustible');
    await page.getByLabel('Monto (MXN)').fill('4000');
    await page.getByRole('button', { name: 'Registrar gasto' }).click();
    await expect(page.getByRole('status')).toContainText('Gasto registrado');
    await expect(page.locator('[data-gasto="Diésel y refacciones"]')).toContainText('$4,000');
    await expect(page.getByTestId('suma')).toContainText('$4,000');

    await page.getByRole('link', { name: 'Panel', exact: true }).click();
    await expect(page.getByText('Pérdida del mes')).toBeVisible();
    await expect(page.getByTestId('ganancia')).toContainText(/-\$520/);
    await expect(page.locator('app-kpi-card', { hasText: 'Gastos del mes' })).toContainText(
      '$4,000',
    );
    await logout(page);
  });

  test('un servicio de mantenimiento con costo se registra también como gasto', async ({
    page,
    request,
  }) => {
    const headers = await adminHeaders(request);
    const plan = await request.post(`/api/admin/equipos/${equipo.id}/mantenimiento`, {
      headers,
      data: { nombre: 'Cambio de aceite', cada_horas: 250 },
    });
    expect(plan.ok(), await plan.text()).toBeTruthy();

    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto(`/admin/equipos/${equipo.id}`);
    const fila = page.locator('[data-plan="Cambio de aceite"]');
    await fila.getByRole('button', { name: 'Servicio realizado' }).click();
    await fila.getByLabel('Costo (opcional)').fill('800');
    await fila.getByRole('button', { name: 'Registrar servicio' }).click();
    await expect(fila).toContainText('Al día');

    await page.goto('/admin/gastos');
    await expect(page.locator('[data-gasto*="Cambio de aceite"]')).toContainText('$800');
    await expect(page.locator('[data-gasto*="Cambio de aceite"]')).toContainText('PAN-A');
    await logout(page);
  });

  test('ventas ve los gastos pero no puede registrarlos ni borrarlos', async ({ page }) => {
    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto('/admin/gastos');
    await expect(page.locator('[data-gasto="Diésel y refacciones"]')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Registrar gasto' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Borrar' })).toHaveCount(0);
    await logout(page);
  });

  test('un administrador puede borrar un gasto', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/gastos');
    await page
      .locator('[data-gasto="Diésel y refacciones"]')
      .getByRole('button', { name: 'Borrar' })
      .click();
    await expect(page.getByRole('status')).toContainText('Gasto borrado');
    await expect(page.locator('[data-gasto="Diésel y refacciones"]')).toHaveCount(0);
    await logout(page);
  });
});
