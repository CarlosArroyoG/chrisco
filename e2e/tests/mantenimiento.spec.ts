import { expect, test } from '@playwright/test';
import { resetDatabase } from '../db';
import { ADMIN, VENTAS } from '../env';
import { adminHeaders, logout, seedEquipos, signIn } from './helpers';

let equipo = { id: '', codigo: 'MAN-A' };

test.beforeAll(() => resetDatabase());

test.describe.serial('Mantenimiento periódico', () => {
  test('preparación: un equipo con 1,000 h', async ({ request }) => {
    [equipo.id] = await seedEquipos(request, 'Categoría Mantenimiento E2E', [
      { codigo: equipo.codigo, nombre: 'Mantenimiento Alfa', horometro: 1000 },
    ]);
  });

  test('el admin da de alta un plan por horas desde la ficha del equipo', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto(`/admin/equipos/${equipo.id}`);
    await expect(page.getByText('Este equipo no tiene planes de mantenimiento.')).toBeVisible();

    // Hace falta al menos un intervalo.
    await page.getByLabel('Servicio', { exact: true }).fill('Cambio de aceite');
    await expect(page.getByRole('button', { name: 'Agregar plan' })).toBeDisabled();
    await page.getByLabel('Cada (horas)').fill('250');
    await page.getByRole('button', { name: 'Agregar plan' }).click();

    const plan = page.locator('[data-plan="Cambio de aceite"]');
    await expect(plan).toContainText('Cada 250 h');
    await expect(plan).toContainText('Al día');
    await expect(plan).toContainText('faltan 250 h');
    await logout(page);
  });

  test('al acercarse y pasarse el horómetro el plan cambia de estado', async ({
    page,
    request,
  }) => {
    const headers = await adminHeaders(request);
    const actual = await (await request.get(`/api/admin/equipos/${equipo.id}`, { headers })).json();
    const subirHorometro = async (valor: number) => {
      const res = await request.put(`/api/admin/equipos/${equipo.id}`, {
        headers,
        data: { ...actual, horometro: valor },
      });
      expect(res.ok(), await res.text()).toBeTruthy();
    };

    await signIn(page, VENTAS.email, VENTAS.password);
    await subirHorometro(1210); // faltan 40 h: próximo
    await page.goto('/admin/mantenimiento');
    const fila = page.locator('[data-plan="Cambio de aceite"]');
    await expect(fila).toContainText('Próximo');
    await expect(fila).toContainText('faltan 40 h');

    await subirHorometro(1260); // se pasó por 10 h: vencido
    await page.reload();
    await expect(fila).toContainText('Vencido');
    await expect(fila).toContainText('se pasó por 10 h');

    // Ventas ve el plan pero no puede cambiarlo.
    await page.goto(`/admin/equipos/${equipo.id}`);
    await expect(page.locator('[data-plan="Cambio de aceite"]')).toContainText('Vencido');
    await expect(page.getByRole('button', { name: 'Servicio realizado' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Agregar plan' })).toHaveCount(0);
    await logout(page);
  });

  test('registrar el servicio realizado reinicia el plan', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto(`/admin/equipos/${equipo.id}`);
    const plan = page.locator('[data-plan="Cambio de aceite"]');
    await expect(plan).toContainText('Vencido');
    await plan.getByRole('button', { name: 'Servicio realizado' }).click();
    await plan.getByLabel('Notas (opcional)').fill('Aceite 15W40 y filtro');
    await plan.getByRole('button', { name: 'Registrar servicio' }).click();

    await expect(plan).toContainText('Al día');
    await expect(plan).toContainText('faltan 250 h');
    await expect(plan).toContainText('1,260 h'); // el último servicio se hizo a 1,260 h

    await page.goto('/admin/mantenimiento');
    await page.getByLabel('Solo lo que requiere atención').check();
    await expect(page.getByText('No hay mantenimientos pendientes.')).toBeVisible();
    await logout(page);
  });

  test('quitar el plan', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto(`/admin/equipos/${equipo.id}`);
    await page.getByRole('button', { name: 'Quitar plan' }).click();
    await expect(page.getByText('Este equipo no tiene planes de mantenimiento.')).toBeVisible();
    await logout(page);
  });
});
