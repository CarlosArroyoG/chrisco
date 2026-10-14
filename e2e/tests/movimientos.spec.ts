import { expect, Page, test } from '@playwright/test';
import { resetDatabase } from '../db';
import { VENTAS } from '../env';
import { createApprovedClient, logout, PNG, seedEquipos, signIn, userHeaders } from './helpers';
import { apartarPorApi, confirmarPorApi, equipoId } from './rentas-api';

const C = {
  email: 'mueve@mueve-e2e.com',
  password: 'cliente-mueve-clave-1',
  rfc: 'MOV010101AB1',
  razonSocial: 'Constructora Mueve SA de CV',
};

let renta = { id: '', folio: '' };

test.beforeAll(() => resetDatabase());

async function registrar(page: Page, boton: string, horometro: string, notas?: string) {
  await page.getByLabel('Horómetro (h)').fill(horometro);
  if (notas) await page.getByLabel('Notas (opcional)').fill(notas);
  await page.getByLabel('Foto del tablero').setInputFiles(PNG);
  await page.getByRole('button', { name: boton }).click();
}

test.describe.serial('Entrega y devolución del equipo', () => {
  test('preparación: una renta confirmada', async ({ request }) => {
    await seedEquipos(request, 'Categoría Movimientos E2E', [
      { codigo: 'MOV-A', nombre: 'Mueve Alfa' },
    ]);
    await createApprovedClient(request, C);
    const cliente = await userHeaders(request, C.email, C.password);
    const ventas = await userHeaders(request, VENTAS.email, VENTAS.password);
    renta = await apartarPorApi(
      request,
      cliente,
      ventas,
      await equipoId(request, cliente, 'MOV-A'),
    );
    await confirmarPorApi(request, cliente, ventas, renta.id);
  });

  test('el cliente ve la renta confirmada pero no puede registrar movimientos', async ({
    page,
  }) => {
    await signIn(page, C.email, C.password);
    await page.goto(`/cliente/rentas/${renta.id}`);
    await expect(page.locator('app-status-badge').getByText('Confirmada')).toBeVisible();
    await expect(page.getByText('El equipo todavía no sale')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Registrar salida' })).toHaveCount(0);
    await logout(page);
  });

  test('ventas registra la salida con horómetro y foto', async ({ page }) => {
    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto(`/admin/rentas/${renta.id}`);
    await expect(page.getByRole('button', { name: 'Registrar salida' })).toBeDisabled();
    await registrar(page, 'Registrar salida', '1200.5', 'Sale con tanque lleno');

    await expect(page.locator('app-status-badge').getByText('En renta')).toBeVisible();
    const salida = page.locator('[data-movimiento="salida"]');
    await expect(salida).toContainText('Horómetro 1,200.5 h');
    await expect(salida).toContainText('Sale con tanque lleno');
    await expect(page.getByRole('button', { name: 'Registrar regreso' })).toBeDisabled();
  });

  test('no se acepta un horómetro menor al de la salida', async ({ page }) => {
    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto(`/admin/rentas/${renta.id}`);
    await registrar(page, 'Registrar regreso', '1100');
    await expect(page.getByRole('alert')).toContainText('menor al de la salida');
    await expect(page.locator('app-status-badge').getByText('En renta')).toBeVisible();
  });

  test('el regreso calcula las horas y deja la renta devuelta', async ({ page }) => {
    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto(`/admin/rentas/${renta.id}`);
    await registrar(page, 'Registrar regreso', '1209');
    await expect(page.locator('app-status-badge').getByText('Devuelta')).toBeVisible();
    await expect(page.getByTestId('horas-usadas')).toContainText('8.5 h');
    await expect(page.getByRole('button', { name: /^Registrar/ })).toHaveCount(0);
    await logout(page);
  });

  test('al confirmar el pago del saldo la renta se cierra', async ({ page }) => {
    // El cliente reporta el saldo y ventas lo confirma.
    await signIn(page, C.email, C.password);
    await page.goto(`/cliente/rentas/${renta.id}`);
    await page.getByLabel('Monto transferido (MXN)').fill('8120');
    await page.getByLabel(/^Comprobante/).setInputFiles(PNG);
    await page.getByRole('button', { name: 'Reportar transferencia' }).click();
    await expect(page.getByLabel('Transferencias')).toContainText('$8,120.00');
    await logout(page);

    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto(`/admin/rentas/${renta.id}`);
    await page.getByRole('button', { name: 'Confirmar pago' }).click();
    await expect(page.getByTestId('saldo')).toContainText('$0.00');
    await page.reload();
    await expect(page.locator('app-status-badge').getByText('Cerrada')).toBeVisible();
    await logout(page);
  });
});
