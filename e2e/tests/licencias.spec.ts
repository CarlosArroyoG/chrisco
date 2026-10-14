import { expect, Page, test } from '@playwright/test';
import { resetDatabase } from '../db';
import { VENTAS } from '../env';
import { createApprovedClient, logout, PNG, seedEquipos, signIn, userHeaders } from './helpers';
import { apartarPorApi, equipoId } from './rentas-api';

const C = {
  email: 'licencia@licencia-e2e.com',
  password: 'cliente-licencia-clave-1',
  rfc: 'LIC010101AB1',
  razonSocial: 'Constructora Licencia SA de CV',
};

let renta = { id: '', folio: '' };

test.beforeAll(() => resetDatabase());

const licencia = (page: Page) => page.locator('[data-requisito="licencia_federal"]');

/** Fecha local `dias` días a partir de hoy, en el formato de `<input type="date">`. */
function dia(dias: number): string {
  const d = new Date();
  d.setDate(d.getDate() + dias);
  return d.toLocaleDateString('en-CA');
}

test.describe.serial('Licencia federal: revisión manual', () => {
  test('preparación: una renta con operador de la empresa cliente', async ({ request }) => {
    await seedEquipos(request, 'Categoría Licencias E2E', [
      { codigo: 'LIC-A', nombre: 'Licencia Alfa' },
    ]);
    await createApprovedClient(request, C);
    const cliente = await userHeaders(request, C.email, C.password);
    const ventas = await userHeaders(request, VENTAS.email, VENTAS.password);
    renta = await apartarPorApi(
      request,
      cliente,
      ventas,
      await equipoId(request, cliente, 'LIC-A'),
      { operador_modo: 'cliente' },
    );
  });

  test('el cliente sube la foto de la licencia del operador', async ({ page }) => {
    await signIn(page, C.email, C.password);
    await page.goto(`/cliente/rentas/${renta.id}`);
    await expect(licencia(page)).toContainText('Licencia federal vigente del operador');
    await expect(licencia(page)).not.toContainText('QR');
    await licencia(page)
      .getByLabel(/^Subir/)
      .setInputFiles(PNG);
    await expect(licencia(page)).toContainText('En revisión');
    await logout(page);
  });

  test('ventas no puede aprobar una licencia vencida y la aprueba con datos válidos', async ({
    page,
  }) => {
    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto(`/admin/rentas/${renta.id}`);
    await licencia(page).getByRole('button', { name: 'Aprobar' }).click();
    await expect(page.getByRole('button', { name: 'Aprobar licencia' })).toBeDisabled();

    await page.getByLabel('Número de licencia').fill('LF-998877');
    await page.getByLabel('Vigente hasta').fill(dia(-1));
    await page.getByRole('button', { name: 'Aprobar licencia' }).click();
    await expect(page.getByRole('alert')).toContainText('antes de que termine la');
    await expect(licencia(page)).toContainText('En revisión');

    await licencia(page).getByRole('button', { name: 'Aprobar' }).click();
    await page.getByLabel('Número de licencia').fill('LF-998877');
    await page.getByLabel('Vigente hasta').fill(dia(365));
    await page.getByRole('button', { name: 'Aprobar licencia' }).click();
    await expect(licencia(page)).toContainText('Cumplido');
    await expect(licencia(page)).toContainText('Licencia LF-998877, vigente hasta');
    await logout(page);
  });
});
