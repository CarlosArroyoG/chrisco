import { expect, Page, test } from '@playwright/test';
import { resetDatabase } from '../db';
import { VENTAS } from '../env';
import { createApprovedClient, logout, PDF, seedEquipos, signIn, userHeaders } from './helpers';
import { mailsTo } from './mail';
import { apartarPorApi, equipoId } from './rentas-api';

const C = {
  email: 'cumple@cumple-e2e.com',
  password: 'cliente-cumple-clave-1',
  rfc: 'CUM010101AB1',
  razonSocial: 'Constructora Cumple SA de CV',
};

let renta = { id: '', folio: '' };
let rentaDos = { id: '', folio: '' };

test.beforeAll(() => resetDatabase());

const requisito = (page: Page, codigo: string) => page.locator(`[data-requisito="${codigo}"]`);

test.describe.serial('Cumplimiento del apartado y cobranza', () => {
  test('preparación: equipos, empresa y dos rentas apartadas', async ({ request }) => {
    await seedEquipos(request, 'Categoría Cumplimiento E2E', [
      { codigo: 'CUM-A', nombre: 'Cumple Alfa' },
      { codigo: 'CUM-B', nombre: 'Cumple Beta' },
    ]);
    await createApprovedClient(request, C);
    const cliente = await userHeaders(request, C.email, C.password);
    const ventas = await userHeaders(request, VENTAS.email, VENTAS.password);
    renta = await apartarPorApi(
      request,
      cliente,
      ventas,
      await equipoId(request, cliente, 'CUM-A'),
    );
    rentaDos = await apartarPorApi(
      request,
      cliente,
      ventas,
      await equipoId(request, cliente, 'CUM-B'),
    );
  });

  test('el cliente ve sus requisitos y sube el contrato y la póliza', async ({ page }) => {
    await signIn(page, C.email, C.password);
    await page.goto(`/cliente/rentas/${renta.id}`);
    const panel = page.getByRole('region', { name: 'Cumplimiento y pagos' });
    await expect(panel).toContainText('$11,600.00');
    await expect(panel).toContainText('$3,480.00');
    await expect(requisito(page, 'contrato')).toContainText('Pendiente');

    await requisito(page, 'contrato')
      .getByLabel(/^Subir/)
      .setInputFiles(PDF);
    await expect(requisito(page, 'contrato')).toContainText('En revisión');
    await requisito(page, 'poliza')
      .getByLabel(/^Subir/)
      .setInputFiles(PDF);
    await expect(requisito(page, 'poliza')).toContainText('En revisión');
    await logout(page);
  });

  test('el cliente reporta la transferencia del anticipo', async ({ page }) => {
    await signIn(page, C.email, C.password);
    await page.goto(`/cliente/rentas/${renta.id}`);
    await page.getByLabel('Monto transferido (MXN)').fill('3480');
    await page.getByLabel(/Referencia o rastreo/).fill('SPEI-E2E-1');
    await page.getByLabel(/^Comprobante/).setInputFiles(PDF);
    await page.getByRole('button', { name: 'Reportar transferencia' }).click();
    await expect(requisito(page, 'anticipo')).toContainText('En revisión');
    await expect(page.getByLabel('Transferencias')).toContainText('SPEI-E2E-1');
    await expect(page.getByTestId('pagado')).toContainText('$0.00'); // aún sin confirmar
    await logout(page);
  });

  test('ventas rechaza la póliza con motivo y el cliente la vuelve a subir', async ({ page }) => {
    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto(`/admin/rentas/${renta.id}`);
    await requisito(page, 'poliza').getByRole('button', { name: 'Rechazar' }).click();
    await page.getByLabel(/Motivo del rechazo/).fill('La póliza está vencida');
    await page.getByRole('button', { name: 'Confirmar rechazo' }).click();
    await expect(requisito(page, 'poliza')).toContainText('Rechazado');
    await expect(requisito(page, 'poliza')).toContainText('La póliza está vencida');
    await logout(page);
    await expect
      .poll(() => mailsTo(C.email).some((m) => m.body.includes('La póliza está vencida')))
      .toBe(true);

    await signIn(page, C.email, C.password);
    await page.goto(`/cliente/rentas/${renta.id}`);
    await expect(requisito(page, 'poliza')).toContainText('Rechazado');
    await requisito(page, 'poliza')
      .getByLabel(/^Subir/)
      .setInputFiles(PDF);
    await expect(requisito(page, 'poliza')).toContainText('En revisión');
    await logout(page);
  });

  test('ventas aprueba todo y la renta se confirma sola', async ({ page }) => {
    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto(`/admin/rentas/${renta.id}`);
    await requisito(page, 'contrato').getByRole('button', { name: 'Aprobar' }).click();
    await expect(requisito(page, 'contrato')).toContainText('Cumplido');
    await requisito(page, 'poliza').getByRole('button', { name: 'Aprobar' }).click();
    await expect(requisito(page, 'poliza')).toContainText('Cumplido');
    await expect(page.locator('app-status-badge').getByText('Apartada')).toBeVisible();

    await page.getByRole('button', { name: 'Confirmar pago' }).click();
    await expect(page.getByTestId('pagado')).toContainText('$3,480.00');
    await expect(page.getByTestId('saldo')).toContainText('$8,120.00');
    await expect(page.locator('app-status-badge').getByText('Confirmada')).toBeVisible();
    await expect(page.getByText('Renta confirmada')).toBeVisible();
    await logout(page);
    await expect
      .poll(() => mailsTo(C.email).some((m) => m.subject.includes('confirmada')))
      .toBe(true);
  });

  test('la cobranza muestra lo cotizado, lo cobrado y lo que falta', async ({ page }) => {
    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto('/admin/cobranza');
    await expect(page.getByTestId('total-cotizado')).toContainText('$23,200.00');
    await expect(page.getByTestId('total-pagado')).toContainText('$3,480.00');
    await expect(page.getByTestId('total-saldo')).toContainText('$19,720.00');
    await expect(page.getByRole('row', { name: new RegExp(renta.folio) })).toContainText(
      '$8,120.00',
    );

    await page.getByLabel('Buscar').fill(rentaDos.folio);
    await expect(page.getByRole('row', { name: new RegExp(rentaDos.folio) })).toBeVisible();
    await expect(page.getByRole('row', { name: new RegExp(renta.folio) })).toHaveCount(0);
    await logout(page);
  });

  test('el cliente no entra a la cobranza del personal', async ({ page }) => {
    await signIn(page, C.email, C.password);
    await page.goto('/admin/cobranza');
    await expect(page).not.toHaveURL(/\/admin\/cobranza/);
    await logout(page);
  });
});
