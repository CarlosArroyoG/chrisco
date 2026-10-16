import { expect, test } from '@playwright/test';
import { resetDatabase } from '../db';
import { ADMIN } from '../env';
import { createApprovedClient, logout, PNG, seedEquipos, signIn } from './helpers';

const CATEGORIA = 'Categoría Fotos E2E';
const EQUIPO = 'Fotos Alfa';
const C = {
  email: 'fotos@fotos-e2e.com',
  password: 'cliente-fotos-clave-1',
  rfc: 'FOT010101AB1',
  razonSocial: 'Constructora Fotos SA de CV',
};

test.beforeAll(() => resetDatabase());

test.describe.serial('Fotos al crear un equipo', () => {
  test('preparación: una categoría y un cliente aprobado', async ({ request }) => {
    await seedEquipos(request, CATEGORIA, []);
    await createApprovedClient(request, C);
  });

  test('al crear el equipo se eligen varias fotos y se ven como carrusel', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/equipos/nuevo');
    await expect(page.getByText('Fotos (0/10)')).toBeVisible();
    await expect(page.getByText('Aún no hay fotos.')).toBeVisible();

    await page.getByLabel('Categoría *').selectOption({ label: CATEGORIA });
    await page.getByLabel('Código *').fill('fot-001');
    await page.getByLabel('Nombre *').fill(EQUIPO);
    await page.getByLabel('Marca *').fill('Caterpillar');
    await page.getByLabel('Modelo *').fill('320');
    await page.getByLabel('Número de serie *').fill('FOT-SN-001');
    await page.getByLabel('Tarifa por hora (MXN)').fill('1850');

    // Las fotos se previsualizan antes de guardar, en un carrusel con miniaturas.
    await page.getByLabel(/Agregar fotos/).setInputFiles([PNG, PNG, PNG]);
    await expect(page.getByText('Fotos (3/10)')).toBeVisible();
    const vista = page.getByRole('group', { name: 'Vista previa' });
    await expect(vista).toContainText('1 / 3');
    await vista.getByRole('button', { name: 'Foto siguiente' }).click({ force: true });
    await expect(vista).toContainText('2 / 3');
    await expect(page.getByAltText('Foto del equipo')).toHaveCount(3);
    await expect(page.getByText('Portada', { exact: true })).toBeVisible();

    // Una foto de más se puede quitar antes de guardar.
    await page.getByRole('button', { name: 'Quitar foto' }).last().click();
    await expect(page.getByText('Fotos (2/10)')).toBeVisible();

    await page.getByRole('button', { name: 'Crear equipo' }).click();
    await expect(page).toHaveURL(/\/admin\/equipos\/[0-9a-f-]{36}$/);
    await expect(page.getByRole('heading', { name: EQUIPO })).toBeVisible();
    await expect(page.getByText('Fotos (2/10)')).toBeVisible();
    await expect(page.getByRole('group', { name: 'Vista previa' })).toContainText('1 / 2');
    // La miniatura debe haberse cargado de verdad (la imagen puede tardar un instante).
    const miniatura = page.getByAltText('Foto del equipo').first();
    await expect
      .poll(() =>
        miniatura.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0),
      )
      .toBe(true);
    await logout(page);
  });

  test('el cliente ve esas fotos como carrusel en el catálogo', async ({ page }) => {
    await signIn(page, C.email, C.password);
    await page.goto('/cliente/catalogo');
    const tarjeta = page.locator(`[data-equipo="${EQUIPO}"]`);
    await expect(tarjeta).toContainText('1 / 2');
    await tarjeta.getByRole('button', { name: 'Foto siguiente' }).click({ force: true });
    await expect(tarjeta).toContainText('2 / 2');
    await logout(page);
  });
});
