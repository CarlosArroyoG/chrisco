import { expect, test } from '@playwright/test';
import { resetDatabase } from '../db';
import { VENTAS } from '../env';
import { createApprovedClient, logout, seedEquipos, signIn, userHeaders } from './helpers';
import { mailsTo } from './mail';
import { equipoId, solicitarPorApi, tomorrowWorkday } from './rentas-api';

const C1 = {
  email: 'uno@cotiza-e2e.com',
  password: 'cliente-uno-clave-1',
  rfc: 'COT010101AB1',
  razonSocial: 'Constructora Uno Cotiza SA de CV',
};
const C2 = {
  email: 'dos@cotiza-e2e.com',
  password: 'cliente-dos-clave-2',
  rfc: 'COT020202XY9',
  razonSocial: 'Constructora Dos Cotiza SA de CV',
};

let renta1 = { id: '', folio: '' };

// Cada archivo parte de un sistema limpio: no depende de lo que dejó otro.
test.beforeAll(() => resetDatabase());

test.describe.serial('Cotización y apartado', () => {
  test('preparación: equipos, dos empresas y una solicitud', async ({ request }) => {
    await seedEquipos(request, 'Categoría Cotizaciones E2E', [
      { codigo: 'COT-A', nombre: 'Cotiza Alfa', requiere_lowboy: true },
      { codigo: 'COT-B', nombre: 'Cotiza Beta' },
      { codigo: 'COT-C', nombre: 'Cotiza Gamma' },
    ]);
    await createApprovedClient(request, C1);
    await createApprovedClient(request, C2);
    const headers = await userHeaders(request, C1.email, C1.password);
    renta1 = await solicitarPorApi(request, headers, await equipoId(request, headers, 'COT-A'));
  });

  test('el cliente espera la cotización', async ({ page }) => {
    await signIn(page, C1.email, C1.password);
    await page.goto(`/cliente/rentas/${renta1.id}`);
    await expect(page.getByRole('heading', { name: renta1.folio })).toBeVisible();
    await expect(page.getByText('Ventas está preparando tu cotización')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Aceptar cotización' })).toHaveCount(0);
    await logout(page);
  });

  test('ventas cotiza partiendo de lo sugerido y ve los totales en vivo', async ({ page }) => {
    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto(`/admin/rentas/${renta1.id}`);
    await expect(page.getByRole('heading', { name: 'Cotizar' })).toBeVisible();

    // Sugerido: renta (10 h × tarifa del equipo), flete y operador de CHRISCO.
    await expect(page.getByLabel('Descripción')).toHaveCount(3);
    await expect(page.getByLabel('Descripción').first()).toHaveValue(/Renta de Cotiza Alfa/);
    await expect(page.getByLabel('Descripción').nth(1)).toHaveValue(/Flete en lowboy/);
    await expect(page.getByLabel('Cant.').first()).toHaveValue('10');
    await expect(page.getByLabel('Precio unitario').first()).toHaveValue('1500');

    // Los servicios llegan en cero: ventas los llena.
    await page.getByLabel('Precio unitario').nth(1).fill('4500');
    await page.getByLabel('Precio unitario').nth(2).fill('350');
    const totales = page.getByLabel('Totales');
    await expect(totales).toContainText('$23,000.00'); // 15,000 + 4,500 + 3,500
    await expect(totales).toContainText('$3,680.00'); // IVA 16 %
    await expect(totales).toContainText('$26,680.00');
    await expect(totales).toContainText('$8,004.00'); // anticipo 30 %

    // Un renglón que se quita se refleja en los totales; uno nuevo, también.
    await page.getByRole('button', { name: 'Quitar' }).nth(2).click();
    await expect(totales).toContainText('$19,500.00');
    await page.getByRole('button', { name: '+ Agregar renglón' }).click();
    await page.getByLabel('Descripción').nth(2).fill('Operador de CHRISCO');
    await page.getByLabel('Precio unitario').nth(2).fill('350');
    await page.getByLabel('Cant.').nth(2).fill('10');
    await expect(totales).toContainText('$26,680.00');

    await page.getByLabel('Notas para el cliente').fill('Incluye seguro de la obra');
    await page.getByRole('button', { name: 'Enviar cotización al cliente' }).click();

    await expect(page.locator('app-status-badge').getByText('Cotizada')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Cotización', exact: true })).toBeVisible();
    await expect(page.getByText('Incluye seguro de la obra')).toBeVisible();
    await logout(page);
    await expect
      .poll(() => mailsTo(C1.email).some((m) => m.subject.includes('está lista')))
      .toBe(true);
  });

  test('el cliente ve la cotización y la acepta: el equipo queda apartado', async ({
    page,
    request,
  }) => {
    await signIn(page, C1.email, C1.password);
    await page.goto(`/cliente/rentas/${renta1.id}`);
    const cotizacion = page.locator('section', {
      has: page.getByRole('heading', { name: 'Cotización', exact: true }),
    });
    await expect(cotizacion).toContainText('Renta de Cotiza Alfa');
    await expect(cotizacion).toContainText('$26,680.00');
    await expect(cotizacion).toContainText('$8,004.00');
    await expect(cotizacion).toContainText(/vigente hasta/);

    await page.getByRole('button', { name: 'Aceptar cotización' }).click();
    await expect(page.locator('app-status-badge').getByText('Apartada')).toBeVisible();
    await expect(page.getByRole('status')).toContainText(
      /Tienes\s+\d+:\d\d\s+para cumplir los requisitos/,
    );
    await expect(cotizacion.getByText('Aceptada', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Aceptar cotización' })).toHaveCount(0);

    // Mientras está apartado, otra empresa no puede pedir el mismo equipo.
    const headersDos = await userHeaders(request, C2.email, C2.password);
    const res = await request.post('/api/rentas/solicitudes', {
      headers: headersDos,
      data: {
        equipo_id: await equipoId(request, headersDos, 'COT-A'),
        ...tomorrowWorkday(),
        destino: 'Otra obra',
        operador_modo: 'chrisco',
        transporte: 'entrega',
      },
    });
    expect(res.status()).toBe(409);
    expect((await res.json()).detail).toContain('no está disponible');
    await logout(page);
  });

  test('ventas ve la renta apartada y le llega el aviso de que el cliente aceptó', async ({
    page,
  }) => {
    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto(`/admin/rentas/${renta1.id}`);
    await expect(page.locator('app-status-badge').getByText('Apartada')).toBeVisible();
    await expect(page.getByRole('status')).toContainText(
      /Faltan\s+\d+:\d\d\s+para que venza el apartado/,
    );
    await expect(page.getByRole('heading', { name: 'Cotizar' })).toHaveCount(0); // ya no se cotiza
    await logout(page);
    await expect
      .poll(() => mailsTo(VENTAS.email).some((m) => m.subject.includes('aceptó la cotización')))
      .toBe(true);
  });

  test('el cliente puede rechazar una cotización y el equipo queda libre', async ({
    page,
    request,
  }) => {
    const headers = await userHeaders(request, C2.email, C2.password);
    const renta = await solicitarPorApi(request, headers, await equipoId(request, headers, 'COT-B'));

    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto(`/admin/rentas/${renta.id}`);
    await expect(page.getByLabel('Descripción')).toHaveCount(3); // renta, entrega y operador
    await page.getByLabel('Precio unitario').nth(1).fill('300');
    await page.getByRole('button', { name: 'Enviar cotización al cliente' }).click();
    await expect(page.locator('app-status-badge').getByText('Cotizada')).toBeVisible();
    await logout(page);

    await signIn(page, C2.email, C2.password);
    await page.goto(`/cliente/rentas/${renta.id}`);
    await page.getByRole('button', { name: 'Rechazar', exact: true }).click();
    await page.getByRole('button', { name: 'Sí, rechazar' }).click();
    await expect(page.locator('app-status-badge').getByText('Cancelada')).toBeVisible();
    await expect(page.getByText('El cliente rechazó la cotización')).toBeVisible();
    await logout(page);

    // El equipo volvió a estar libre: se puede pedir de nuevo.
    const otra = await solicitarPorApi(request, headers, await equipoId(request, headers, 'COT-B'));
    expect(otra.folio).toMatch(/^CHR-/);
  });

  test('ventas puede rechazar una solicitud con un motivo que le llega al cliente', async ({
    page,
    request,
  }) => {
    const headers = await userHeaders(request, C1.email, C1.password);
    const renta = await solicitarPorApi(request, headers, await equipoId(request, headers, 'COT-C'));

    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto(`/admin/rentas/${renta.id}`);
    await page
      .getByLabel(/No podemos atender esta solicitud/)
      .fill('El equipo está en taller esa semana');
    await page.getByRole('button', { name: 'Rechazar solicitud' }).click();
    await expect(page.locator('app-status-badge').getByText('Rechazada')).toBeVisible();
    await expect(page.getByText('El equipo está en taller esa semana')).toBeVisible();
    await logout(page);

    await signIn(page, C1.email, C1.password);
    await page.goto(`/cliente/rentas/${renta.id}`);
    await expect(page.getByText('El equipo está en taller esa semana')).toBeVisible();
    await logout(page);
    await expect
      .poll(() => mailsTo(C1.email).some((m) => m.body.includes('en taller')))
      .toBe(true);
  });

  test('una nueva versión de la cotización reemplaza a la anterior', async ({ page, request }) => {
    const headers = await userHeaders(request, C2.email, C2.password);
    const renta = await solicitarPorApi(request, headers, await equipoId(request, headers, 'COT-C'));

    await signIn(page, VENTAS.email, VENTAS.password);
    await page.goto(`/admin/rentas/${renta.id}`);
    await page.getByRole('button', { name: 'Enviar cotización al cliente' }).click();
    await expect(page.getByText(/Versión 1/)).toBeVisible();

    await page.getByRole('button', { name: 'Cambiar la cotización' }).click();
    await page.getByLabel('Precio unitario').first().fill('1000');
    await page.getByRole('button', { name: 'Enviar cotización al cliente' }).click();
    await expect(page.getByText(/Versión 2/)).toBeVisible();
    await expect(page.getByText(/Versión 1/)).toHaveCount(0);
    await logout(page);

    await signIn(page, C2.email, C2.password);
    await page.goto(`/cliente/rentas/${renta.id}`);
    await expect(page.getByText(/Versión 2/)).toBeVisible();
  });
});
