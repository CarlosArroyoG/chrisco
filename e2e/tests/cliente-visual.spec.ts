import { expect, test } from '@playwright/test';
import { resetDatabase } from '../db';
import { VENTAS } from '../env';
import {
  adminHeaders,
  createApprovedClient,
  logout,
  PNG,
  seedEquipos,
  signIn,
  userHeaders,
} from './helpers';
import { equipoId, solicitarPorApi } from './rentas-api';

const C = {
  email: 'visual@visual-e2e.com',
  password: 'cliente-visual-clave-1',
  rfc: 'VIS010101AB1',
  razonSocial: 'Constructora Visual SA de CV',
};
const DESCRIPCION = 'Excavadora de 20 toneladas, ideal para zanjas y cimentaciones.';

let renta = { id: '', folio: '' };

test.beforeAll(() => resetDatabase());

const tarjeta = (page: import('@playwright/test').Page) =>
  page.locator('[data-equipo="Visual Alfa"]');

test.describe.serial('Experiencia visual del cliente', () => {
  test('preparación: equipos con descripción y varias fotos', async ({ request }) => {
    const [alfa] = await seedEquipos(request, 'Categoría Visual E2E', [
      { codigo: 'VIS-A', nombre: 'Visual Alfa', descripcion: DESCRIPCION },
      { codigo: 'VIS-B', nombre: 'Visual Beta' },
    ]);
    const headers = await adminHeaders(request);
    for (let i = 0; i < 3; i++) {
      const res = await request.post(`/api/admin/equipos/${alfa}/fotos`, {
        headers,
        multipart: { foto: PNG },
      });
      expect(res.ok(), await res.text()).toBeTruthy();
    }
    await createApprovedClient(request, C);
  });

  test('la tarjeta muestra la descripción y un carrusel de fotos', async ({ page }) => {
    await signIn(page, C.email, C.password);
    await page.goto('/cliente/catalogo');
    const alfa = tarjeta(page);
    await expect(alfa).toContainText(DESCRIPCION);
    await expect(alfa).toContainText('Disponible hoy');
    await expect(alfa).toContainText('1 / 3');
    await alfa.getByRole('button', { name: 'Foto siguiente' }).click({ force: true });
    await expect(alfa).toContainText('2 / 3');
    await alfa.getByRole('button', { name: 'Ir a la foto 3' }).click({ force: true });
    await expect(alfa).toContainText('3 / 3');
    // Un equipo con una sola foto (o ninguna) no muestra flechas.
    await expect(
      page.locator('[data-equipo="Visual Beta"]').getByRole('button', { name: 'Foto siguiente' }),
    ).toHaveCount(0);
    await logout(page);
  });

  test('«Disponibles hoy» y «Rentados» filtran por la situación del equipo', async ({ page }) => {
    await signIn(page, C.email, C.password);
    await page.goto('/cliente/catalogo');
    await expect(page.getByRole('heading', { name: 'Catálogo de maquinaria (2)' })).toBeVisible();
    await page.getByRole('button', { name: 'Rentados' }).click();
    await expect(page.getByRole('heading', { name: 'Catálogo de maquinaria (0)' })).toBeVisible();
    await expect(page.getByText('No encontramos equipos con esos filtros.')).toBeVisible();
    await page.getByRole('button', { name: 'Disponibles hoy' }).click();
    await expect(page.getByRole('heading', { name: 'Catálogo de maquinaria (2)' })).toBeVisible();
    await logout(page);
  });

  test('«Reservar este equipo» lleva a la ficha, con galería y descripción', async ({ page }) => {
    await signIn(page, C.email, C.password);
    await page.goto('/cliente/catalogo');
    await tarjeta(page).getByRole('link', { name: 'Reservar este equipo' }).click();
    await expect(page).toHaveURL(/#solicitar$/);
    await expect(page.getByRole('heading', { name: 'Visual Alfa' })).toBeVisible();
    await expect(page.getByText('Acerca de este equipo')).toBeVisible();
    await expect(page.getByText(DESCRIPCION)).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Solicitar este equipo' })).toBeInViewport();

    // La galería: las miniaturas cambian la foto del carrusel.
    await page.getByRole('button', { name: 'Ver foto 3' }).click();
    await expect(page.getByRole('group', { name: 'Visual Alfa' })).toContainText('3 / 3');
    await logout(page);
  });

  test('el botón sigue la etapa de la renta: solicitada, cotizada y apartada', async ({
    page,
    request,
  }) => {
    const cliente = await userHeaders(request, C.email, C.password);
    const ventas = await userHeaders(request, VENTAS.email, VENTAS.password);
    renta = await solicitarPorApi(request, cliente, await equipoId(request, cliente, 'VIS-A'), {
      transporte: 'recoge',
    });

    await signIn(page, C.email, C.password);
    await page.goto('/cliente/catalogo');
    await expect(tarjeta(page)).toContainText(`Solicitud enviada · ${renta.folio}`);
    await expect(tarjeta(page).getByRole('link', { name: 'Ver mi solicitud' })).toBeVisible();
    await expect(tarjeta(page).getByRole('link', { name: 'Reservar este equipo' })).toHaveCount(0);

    const cot = await request.post(`/api/rentas/${renta.id}/cotizacion`, {
      headers: ventas,
      data: {
        partidas: [
          {
            concepto: 'renta',
            descripcion: 'Renta',
            cantidad: 10,
            unidad: 'hora',
            precio_unitario: 1000,
          },
        ],
      },
    });
    expect(cot.ok(), await cot.text()).toBeTruthy();
    await page.reload();
    await expect(tarjeta(page)).toContainText('Cotización lista');
    await tarjeta(page).getByRole('link', { name: 'Revisar cotización' }).click();
    await expect(page.getByRole('heading', { name: renta.folio })).toBeVisible();
    await page.getByRole('button', { name: 'Aceptar cotización' }).click();
    await expect(page.locator('app-status-badge').getByText('Apartada')).toBeVisible();

    await page.goto('/cliente/catalogo');
    await expect(tarjeta(page)).toContainText('Equipo apartado');
    await expect(
      tarjeta(page).getByRole('link', { name: 'Completar requisitos y pagar' }),
    ).toBeVisible();

    // En la ficha, la misma etapa con su línea de avance.
    await tarjeta(page).getByRole('link', { name: 'Visual Alfa' }).click();
    await expect(page.getByText('Paso 3 de 6 · Apartado')).toBeVisible();
    await logout(page);
  });

  test('«Mis rentas» muestra la renta como tarjeta y la mueve de pestaña al cancelarla', async ({
    page,
  }) => {
    await signIn(page, C.email, C.password);
    await page.goto('/cliente/rentas');
    await expect(page.getByRole('heading', { name: 'Mis rentas (1)' })).toBeVisible();
    await expect(page.getByLabel('Requieren tu atención')).toContainText(
      'Una renta necesita tu atención',
    );
    const card = page.locator(`[data-folio="${renta.folio}"]`);
    await expect(card).toContainText('Visual Alfa');
    await expect(card).toContainText('Equipo apartado');
    await expect(card).toContainText('$11,600');
    await expect(page.getByRole('tab', { name: /Activas/ })).toContainText('1');

    await card.getByRole('link', { name: 'Completar requisitos y pagar' }).click();
    await page.getByRole('button', { name: 'Cancelar solicitud' }).click();
    await page.getByRole('button', { name: 'Sí, cancelar' }).click();
    await expect(page.locator('app-status-badge').getByText('Cancelada')).toBeVisible();

    await page.goto('/cliente/rentas');
    await expect(page.getByText('No tienes rentas en curso.')).toBeVisible();
    await page.getByRole('tab', { name: /Canceladas y vencidas/ }).click();
    await expect(page.locator(`[data-folio="${renta.folio}"]`)).toContainText('Cancelada');
    await logout(page);
  });
});
