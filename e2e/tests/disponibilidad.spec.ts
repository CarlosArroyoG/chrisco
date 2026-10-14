import { resetDatabase } from '../db';
import { expect, test } from '@playwright/test';
import { ADMIN, VENTAS } from '../env';
import { createApprovedClient, logout, seedEquipos, signIn } from './helpers';

const CLIENT = {
  email: 'cliente@disponibilidad-e2e.com',
  password: 'cliente-clave-larga-2',
  rfc: 'DIS010101AB1',
  razonSocial: 'Constructora Disponibilidad E2E SA de CV',
};
const MOTIVO = 'Cambio de aceite E2E';

/** Formato de un `<input type="datetime-local">` (hora local) a `horas` de distancia de ahora. */
function inHours(horas: number): string {
  const d = new Date(Date.now() + horas * 3600_000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// Cada archivo parte de un sistema limpio: no depende de lo que dejó otro.
test.beforeAll(() => resetDatabase());

test.describe.serial('Disponibilidad y bloqueos de equipos', () => {
  test('preparación: equipos y un cliente aprobado', async ({ request }) => {
    await seedEquipos(request, 'Categoría Disponibilidad E2E', [
      { codigo: 'DISP-A', nombre: 'Disp Alfa' },
      { codigo: 'DISP-B', nombre: 'Disp Beta' },
    ]);
    await createApprovedClient(request, CLIENT);
  });

  test('un equipo sin bloqueos figura como libre', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/equipos');
    await page.getByLabel('Buscar').fill('Disp');
    await expect(page.getByRole('heading', { name: 'Equipos (2)' })).toBeVisible();
    for (const fila of await page.getByRole('row').filter({ hasText: 'DISP-' }).all()) {
      await expect(fila.getByText('Libre')).toBeVisible();
    }
  });

  test('el admin programa un mantenimiento y el equipo pasa a «En mantenimiento»', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/equipos');
    await page.getByLabel('Buscar').fill('DISP-A');
    await expect(page.getByRole('heading', { name: 'Equipos (1)' })).toBeVisible();
    await page.getByRole('link', { name: 'Editar' }).click();
    await expect(page.getByLabel('Código *')).toHaveValue('DISP-A');
    await expect(page.getByText('el equipo está libre')).toBeVisible();

    // Un bloqueo que ya está en curso: ahora mismo el equipo no se puede usar.
    await page.getByLabel('Desde').fill(inHours(-1));
    await page.getByLabel('Hasta').fill(inHours(3));
    await page.getByLabel('Motivo').fill(MOTIVO);
    await page.getByRole('button', { name: 'Bloquear equipo' }).click();

    await expect(page.getByRole('listitem').filter({ hasText: MOTIVO })).toContainText('Mantenimiento');
    await expect(page.getByRole('listitem').filter({ hasText: MOTIVO })).toContainText(ADMIN.name);
    await expect(page.locator('app-status-badge').getByText('En mantenimiento')).toBeVisible(); // junto al título
  });

  test('no se puede bloquear dos veces el mismo periodo', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/equipos');
    await page.getByLabel('Buscar').fill('DISP-A');
    await expect(page.getByRole('heading', { name: 'Equipos (1)' })).toBeVisible();
    await page.getByRole('link', { name: 'Editar' }).click();
    await expect(page.getByLabel('Código *')).toHaveValue('DISP-A');

    await page.getByLabel('Desde').fill(inHours(1));
    await page.getByLabel('Hasta').fill(inHours(5));
    await page.getByLabel('Motivo').fill('Intento repetido');
    await page.getByRole('button', { name: 'Bloquear equipo' }).click();
    await expect(page.getByRole('alert')).toContainText('no está disponible en ese periodo');
    await expect(page.getByRole('listitem').filter({ hasText: 'Intento repetido' })).toHaveCount(0);

    // Un fin anterior al inicio ni siquiera se envía.
    await page.getByLabel('Desde').fill(inHours(10));
    await page.getByLabel('Hasta').fill(inHours(8));
    await page.getByRole('button', { name: 'Bloquear equipo' }).click();
    await expect(page.getByRole('alert')).toContainText('el fin sea posterior al inicio');
  });

  test('la lista de equipos muestra la situación de cada uno', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/equipos');
    await page.getByLabel('Buscar').fill('Disp');
    await expect(page.getByRole('heading', { name: 'Equipos (2)' })).toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: 'DISP-A' })).toContainText('En mantenimiento');
    await expect(page.getByRole('row').filter({ hasText: 'DISP-B' })).toContainText('Libre');
  });

  test('ventas ve los bloqueos pero no puede crearlos ni liberarlos', async ({ page }) => {
    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto('/admin/equipos');
    await page.getByLabel('Buscar').fill('DISP-A');
    await expect(page.getByRole('heading', { name: 'Equipos (1)' })).toBeVisible();
    await page.getByRole('link', { name: 'Ver' }).click();
    await expect(page.getByLabel('Código *')).toHaveValue('DISP-A');
    await expect(page.getByRole('listitem').filter({ hasText: MOTIVO })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Bloquear equipo' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Liberar' })).toHaveCount(0);
  });

  test('el cliente ve qué equipos están libres en las fechas que necesita', async ({ page }) => {
    await signIn(page, CLIENT.email, CLIENT.password);
    await page.getByRole('link', { name: 'Ver catálogo de maquinaria' }).click();
    await page.getByLabel('Buscar').fill('Disp');
    await expect(page.getByRole('heading', { name: 'Catálogo de maquinaria (2)' })).toBeVisible();

    // Sin fechas no se afirma nada sobre la disponibilidad.
    await expect(page.getByText('en esas fechas')).toHaveCount(0);

    // Un periodo a medias avisa en vez de consultar.
    await page.getByLabel('Lo necesito desde').fill(inHours(1));
    await expect(page.getByText('Elige un inicio y un fin')).toBeVisible();

    // Dentro del mantenimiento: Alfa ocupado, Beta libre.
    await page.getByLabel('Hasta').fill(inHours(2));
    const alfa = page.getByRole('link', { name: /Disp Alfa/ });
    const beta = page.getByRole('link', { name: /Disp Beta/ });
    await expect(alfa).toContainText('Ocupado en esas fechas');
    await expect(beta).toContainText('Disponible en esas fechas');

    await page.getByLabel('Solo disponibles').check();
    await expect(page.getByRole('heading', { name: 'Catálogo de maquinaria (1)' })).toBeVisible();
    await expect(alfa).toHaveCount(0);
    await expect(beta).toBeVisible();

    // Después del mantenimiento Alfa vuelve a estar libre.
    await page.getByLabel('Lo necesito desde').fill(inHours(48));
    await page.getByLabel('Hasta').fill(inHours(50));
    await expect(page.getByRole('heading', { name: 'Catálogo de maquinaria (2)' })).toBeVisible();
    await expect(alfa).toContainText('Disponible en esas fechas');
  });

  test('la ficha del equipo muestra sus periodos ocupados, sin decir por qué', async ({ page }) => {
    await signIn(page, CLIENT.email, CLIENT.password);
    await page.goto('/cliente/catalogo');
    await page.getByLabel('Buscar').fill('Disp Alfa');
    await expect(page.getByRole('heading', { name: 'Catálogo de maquinaria (1)' })).toBeVisible();
    await page.getByRole('link', { name: /Disp Alfa/ }).click();
    await expect(page.getByText(/Ocupado del/)).toHaveCount(1);
    await expect(page.getByText(MOTIVO)).toHaveCount(0);
    await expect(page.getByText('Mantenimiento')).toHaveCount(0);

    await page.goBack();
    await page.getByLabel('Buscar').fill('Disp Beta');
    await expect(page.getByRole('heading', { name: 'Catálogo de maquinaria (1)' })).toBeVisible();
    await page.getByRole('link', { name: /Disp Beta/ }).click();
    await expect(page.getByText('Sin reservas: disponible en cualquier fecha.')).toBeVisible();
  });

  test('al liberar el bloqueo el equipo vuelve a quedar libre', async ({ page, browser }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/equipos');
    await page.getByLabel('Buscar').fill('DISP-A');
    await expect(page.getByRole('heading', { name: 'Equipos (1)' })).toBeVisible();
    await page.getByRole('link', { name: 'Editar' }).click();
    await expect(page.getByLabel('Código *')).toHaveValue('DISP-A');
    await page.getByRole('button', { name: 'Liberar' }).click();
    await expect(page.getByText('el equipo está libre')).toBeVisible();
    await expect(page.locator('app-status-badge').getByText('Libre')).toBeVisible();

    const cliente = await (await browser.newContext()).newPage();
    await signIn(cliente, CLIENT.email, CLIENT.password);
    await cliente.getByRole('link', { name: 'Ver catálogo de maquinaria' }).click();
    await cliente.getByLabel('Buscar').fill('Disp');
    await cliente.getByLabel('Lo necesito desde').fill(inHours(1));
    await cliente.getByLabel('Hasta').fill(inHours(2));
    await cliente.getByLabel('Solo disponibles').check();
    await expect(cliente.getByRole('heading', { name: 'Catálogo de maquinaria (2)' })).toBeVisible();
    await logout(cliente);
  });
});
