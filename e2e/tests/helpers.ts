import { APIRequestContext, expect, Page } from '@playwright/test';
import { ADMIN } from '../env';
import { linkFromMail } from './mail';

export const PDF = {
  name: 'constancia.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from('%PDF-1.4\n% e2e\n%%EOF'),
};

/** PNG válido de 1x1 píxel: basta para probar la subida y el procesamiento de fotos. */
export const PNG = {
  name: 'foto.png',
  mimeType: 'image/png',
  buffer: Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
    'base64',
  ),
};

export async function login(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Correo').fill(email);
  await page.getByLabel('Contraseña').fill(password);
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
}

/** Inicia sesión y espera a que termine (el login correcto sale de /login). */
export async function signIn(page: Page, email: string, password: string): Promise<void> {
  await login(page, email, password);
  await expect(page).not.toHaveURL(/\/login$/);
}

export async function logout(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Salir' }).click();
  await expect(page).toHaveURL(/\/login$/);
}

export interface ClientData {
  email: string;
  password: string;
  rfc: string;
  razonSocial: string;
}

/** Deja una empresa cliente registrada, con correo confirmado y aprobada, usando solo la API. */
export async function createApprovedClient(request: APIRequestContext, data: ClientData): Promise<void> {
  const registro = await request.post('/api/empresa/registro', {
    multipart: {
      razon_social: data.razonSocial,
      sitio_web: 'https://cliente-e2e.com',
      rfc: data.rfc,
      full_name: 'Cliente E2E',
      email: data.email,
      password: data.password,
      constancia: PDF,
    },
  });
  expect(registro.ok(), await registro.text()).toBeTruthy();

  const token = new URL(await linkFromMail(data.email, 'Confirma tu correo')).searchParams.get('token');
  expect((await request.post('/api/auth/verify-email', { data: { token } })).ok()).toBeTruthy();

  const session = await request.post('/api/auth/login', {
    data: { email: ADMIN.email, password: ADMIN.password },
  });
  const headers = { Authorization: `Bearer ${(await session.json()).access_token}` };
  const pendientes = await (await request.get('/api/admin/empresas?status_filter=pendiente', { headers })).json();
  const empresa = pendientes.find((e: { rfc: string }) => e.rfc === data.rfc);
  expect(empresa, 'la empresa recién registrada debe aparecer pendiente').toBeTruthy();
  expect((await request.post(`/api/admin/empresas/${empresa.id}/aprobar`, { headers })).ok()).toBeTruthy();
}
