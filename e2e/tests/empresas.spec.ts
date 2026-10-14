import { expect, test } from '@playwright/test';
import { ADMIN, VENTAS } from '../env';
import { login, logout, PDF } from './helpers';
import { linkFromMail, mailsTo } from './mail';

const OWNER = { email: 'titular@constructora-e2e.com', password: 'titular-clave-larga-1', name: 'Titular E2E' };
const GUEST = { email: 'compa@constructora-e2e.com', password: 'invitado-clave-larga-1', name: 'Compañero E2E' };
const THIRD = { email: 'tercero@constructora-e2e.com', name: 'Tercero E2E' };

// Una sola historia continua: cada paso depende del anterior.
test.describe.serial('Registro, revisión y equipo de una empresa', () => {
  test('rutas protegidas piden iniciar sesión', async ({ page }) => {
    for (const route of ['/admin', '/cliente', '/operador', '/']) {
      await page.goto(route);
      await expect(page).toHaveURL(/\/login$/);
    }
  });

  test('el registro valida los datos antes de enviar', async ({ page }) => {
    await page.goto('/registro');
    await expect(page.getByRole('button', { name: 'Registrar empresa' })).toBeDisabled();

    await page.getByLabel('Razón social').fill('Constructora E2E SA de CV');
    await page.getByLabel('RFC').fill('NO-ES-UN-RFC');
    await page.getByLabel('Página web').fill('constructora-e2e.com');
    await page.getByLabel('Constancia de situación fiscal (PDF)').setInputFiles(PDF);
    await page.getByLabel('Nombre').fill(OWNER.name);
    await page.getByLabel('Correo').fill(OWNER.email);
    await page.getByLabel('Contraseña (mínimo 10 caracteres)').fill(OWNER.password);
    await page.getByRole('button', { name: 'Registrar empresa' }).click();
    await expect(page.getByRole('alert')).toContainText('RFC: El RFC no tiene un formato válido');
  });

  test('registra la empresa y avisa que debe confirmar su correo', async ({ page }) => {
    await page.goto('/registro');
    await page.getByLabel('Razón social').fill('Constructora E2E SA de CV');
    await page.getByLabel('RFC').fill('cce010101ab1');
    await page.getByLabel('Página web').fill('constructora-e2e.com');
    await page.getByLabel('Constancia de situación fiscal (PDF)').setInputFiles(PDF);
    await page.getByLabel('Nombre').fill(OWNER.name);
    await page.getByLabel('Correo').fill(OWNER.email);
    await page.getByLabel('Contraseña (mínimo 10 caracteres)').fill(OWNER.password);
    await page.getByRole('button', { name: 'Registrar empresa' }).click();
    await expect(page.getByRole('status')).toContainText('Registro recibido');
  });

  test('no deja entrar sin confirmar el correo y permite reenviarlo', async ({ page }) => {
    await login(page, OWNER.email, OWNER.password);
    await expect(page.getByRole('alert')).toContainText('Confirma tu correo');
    await page.getByRole('button', { name: 'Reenviar el correo de confirmación' }).click();
    await expect(page.getByRole('status')).toContainText('nuevo enlace');
    await expect.poll(() => mailsTo(OWNER.email).length).toBe(2);
  });

  test('el enlace del correo confirma la cuenta', async ({ page }) => {
    await page.goto(await linkFromMail(OWNER.email, 'Confirma tu correo'));
    await expect(page.getByRole('status')).toContainText('Tu correo quedó confirmado');
  });

  test('el titular ve su empresa pendiente de revisión', async ({ page }) => {
    await login(page, OWNER.email, OWNER.password);
    await expect(page).toHaveURL(/\/cliente$/);
    await expect(page.getByRole('heading', { name: 'Constructora E2E SA de CV' })).toBeVisible();
    await expect(page.getByText('Pendiente de revisión')).toBeVisible();
    await expect(page.getByText('CCE010101AB1')).toBeVisible();
    // Pendiente: aún no hay equipo de usuarios.
    await expect(page.getByText('Usuarios de tu empresa')).toHaveCount(0);

    // Un cliente no entra al panel del personal.
    await page.goto('/admin');
    await expect(page).toHaveURL(/\/cliente$/);
    await logout(page);
  });

  test('ventas ve la empresa y su constancia pero no puede decidir', async ({ page, context }) => {
    await login(page, VENTAS.email, VENTAS.password);
    await expect(page).toHaveURL(/\/admin$/);
    await page.getByRole('link', { name: 'Revisar' }).click();
    await expect(page.getByRole('heading', { name: 'Constructora E2E SA de CV' })).toBeVisible();
    await expect(page.getByText('Solo un administrador puede aprobar o rechazar.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Aprobar empresa' })).toHaveCount(0);

    const popup = context.waitForEvent('page');
    await page.getByRole('button', { name: /Ver constancia/ }).click();
    expect((await popup).url()).toMatch(/^blob:/);
    await logout(page);
  });

  test('el admin rechaza la empresa con un motivo', async ({ page }) => {
    await login(page, ADMIN.email, ADMIN.password);
    await expect(page.getByRole('cell', { name: 'Constructora E2E SA de CV' })).toBeVisible();
    await page.getByRole('link', { name: 'Revisar' }).click();
    await page.getByLabel(/Motivo del rechazo/).fill('La constancia no es legible');
    await page.getByRole('button', { name: 'Rechazar' }).click();
    await expect(page.getByText('Motivo del rechazo: La constancia no es legible')).toBeVisible();

    await page.getByRole('link', { name: '← Volver a empresas' }).click();
    await expect(page.getByText('No hay empresas en esta lista.')).toBeVisible(); // ya no está en Pendientes
    await logout(page);
    await expect.poll(() => mailsTo(OWNER.email).some((m) => m.body.includes('La constancia no es legible'))).toBe(true);
  });

  test('el titular corrige y reenvía a revisión', async ({ page }) => {
    await login(page, OWNER.email, OWNER.password);
    await expect(page.getByRole('alert')).toContainText('Motivo: La constancia no es legible');
    await page.getByLabel('Nueva constancia de situación fiscal (PDF)').setInputFiles(PDF);
    await page.getByLabel('Razón social').fill('Constructora E2E Corregida SA de CV');
    await page.getByRole('button', { name: 'Reenviar a revisión' }).click();
    await expect(page.getByText('Pendiente de revisión')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Constructora E2E Corregida SA de CV' })).toBeVisible();
    await logout(page);
  });

  test('el admin aprueba la empresa', async ({ page }) => {
    await login(page, ADMIN.email, ADMIN.password);
    await page.getByRole('link', { name: 'Revisar' }).click();
    await page.getByRole('button', { name: 'Aprobar empresa' }).click();
    await expect(page.getByText('Aprobada', { exact: true })).toBeVisible();
    await logout(page);
    await expect.poll(() => mailsTo(OWNER.email).some((m) => m.subject.includes('aprobada'))).toBe(true);
  });

  test('el titular invita a un compañero, que crea su contraseña y entra', async ({ page, browser }) => {
    await login(page, OWNER.email, OWNER.password);
    await expect(page.getByText('Usuarios de tu empresa (1/3)')).toBeVisible();
    await page.getByLabel('Nombre').fill(GUEST.name);
    await page.getByLabel('Correo').fill(GUEST.email);
    await page.getByRole('button', { name: 'Enviar invitación' }).click();
    await expect(page.getByText('Usuarios de tu empresa (2/3)')).toBeVisible();
    await expect(page.getByText('Invitación pendiente')).toBeVisible();

    // El invitado, en otra sesión.
    const guestPage = await (await browser.newContext()).newPage();
    await guestPage.goto(await linkFromMail(GUEST.email, 'te invitó'));
    await guestPage.getByLabel(/Contraseña/).fill(GUEST.password);
    await guestPage.getByRole('button', { name: 'Guardar contraseña' }).click();
    await expect(guestPage.getByRole('status')).toContainText('Contraseña guardada');
    await login(guestPage, GUEST.email, GUEST.password);
    await expect(guestPage).toHaveURL(/\/cliente$/);
    await expect(guestPage.getByText('Usuarios de tu empresa (2/3)')).toBeVisible();
    // El invitado ve al equipo pero no puede invitar ni dar de baja.
    await expect(guestPage.getByRole('button', { name: 'Enviar invitación' })).toHaveCount(0);
    await expect(guestPage.getByRole('button', { name: 'Dar de baja' })).toHaveCount(0);
  });

  test('el máximo es de 3 usuarios y dar de baja libera un lugar', async ({ page }) => {
    await login(page, OWNER.email, OWNER.password);
    await page.getByLabel('Nombre').fill(THIRD.name);
    await page.getByLabel('Correo').fill(THIRD.email);
    await page.getByRole('button', { name: 'Enviar invitación' }).click();
    await expect(page.getByText('Usuarios de tu empresa (3/3)')).toBeVisible();
    await expect(page.getByText('Llegaste al máximo de usuarios')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Enviar invitación' })).toHaveCount(0);

    await page.getByRole('listitem').filter({ hasText: THIRD.email }).getByRole('button', { name: 'Dar de baja' }).click();
    await expect(page.getByText('Usuarios de tu empresa (2/3)')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Enviar invitación' })).toBeVisible();
    await logout(page);
  });

  test('recuperar la contraseña con el enlace del correo', async ({ page }) => {
    const nueva = 'titular-clave-nueva-2';
    await page.goto('/login');
    await page.getByRole('link', { name: '¿Olvidaste tu contraseña?' }).click();
    await page.getByLabel('Correo').fill(OWNER.email);
    await page.getByRole('button', { name: 'Enviar enlace' }).click();
    await expect(page.getByRole('status')).toContainText('recibirás un enlace');

    await page.goto(await linkFromMail(OWNER.email, 'Recupera tu contraseña'));
    await page.getByLabel(/Contraseña/).fill(nueva);
    await page.getByRole('button', { name: 'Guardar contraseña' }).click();
    await expect(page.getByRole('status')).toContainText('Contraseña guardada');

    await login(page, OWNER.email, OWNER.password);
    await expect(page.getByRole('alert')).toContainText('incorrectos');
    await login(page, OWNER.email, nueva);
    await expect(page).toHaveURL(/\/cliente$/);
  });

  test('la sesión sobrevive a recargar la página', async ({ page }) => {
    await login(page, ADMIN.email, ADMIN.password);
    await expect(page).toHaveURL(/\/admin$/);
    await page.reload();
    await expect(page).toHaveURL(/\/admin$/);
    await expect(page.getByRole('heading', { name: 'Empresas clientes' })).toBeVisible();
  });
});
