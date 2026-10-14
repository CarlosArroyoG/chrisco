import { expect, test } from '@playwright/test';
import { resetDatabase } from '../db';
import { VENTAS } from '../env';
import { createApprovedClient, logout, seedEquipos, signIn, userHeaders } from './helpers';

const C1 = {
  email: 'uno@rentas-e2e.com',
  password: 'cliente-uno-clave-1',
  rfc: 'REN010101AB1',
  razonSocial: 'Constructora Uno E2E SA de CV',
};
const C2 = {
  email: 'dos@rentas-e2e.com',
  password: 'cliente-dos-clave-2',
  rfc: 'REN020202XY9',
  razonSocial: 'Constructora Dos E2E SA de CV',
};
const DESTINO = 'Autopista Morelia - Guadalajara km 45';

let folio = '';

// Cada archivo parte de un sistema limpio: no depende de lo que dejó otro.
test.beforeAll(() => resetDatabase());

test.describe.serial('Solicitud de renta', () => {
  test('preparación: equipos y dos empresas aprobadas', async ({ request }) => {
    await seedEquipos(request, 'Categoría Rentas E2E', [
      { codigo: 'REN-A', nombre: 'Renta Alfa', requiere_lowboy: true },
      { codigo: 'REN-B', nombre: 'Renta Beta' },
      { codigo: 'REN-C', nombre: 'Renta Gamma' },
      { codigo: 'REN-D', nombre: 'Renta Delta' },
      { codigo: 'REN-E', nombre: 'Renta Épsilon' },
    ]);
    await createApprovedClient(request, C1);
    await createApprovedClient(request, C2);
  });

  test('el cliente pide un equipo: revisa los requisitos, lo reserva y recibe el mensaje', async ({
    page,
  }) => {
    await signIn(page, C1.email, C1.password);
    await page.getByRole('link', { name: 'Ver catálogo de maquinaria' }).click();
    await page.getByLabel('Buscar').fill('Renta Alfa');
    await expect(page.getByRole('heading', { name: 'Catálogo de maquinaria (1)' })).toBeVisible();
    await page.getByRole('link', { name: /Renta Alfa/ }).click();

    await expect(page.getByRole('heading', { name: 'Solicitar este equipo' })).toBeVisible();
    await expect(page.getByLabel('Lo necesito desde *')).not.toHaveValue(''); // sugiere mañana
    await expect(page.getByLabel('Hasta *')).not.toHaveValue('');

    // Faltan datos: no avanza.
    await page.getByRole('button', { name: 'Revisar solicitud' }).click();
    await expect(page.getByRole('alert')).toContainText('Indica el periodo');

    await page.getByLabel('Lugar donde se usará *').fill(DESTINO);
    await page.getByLabel('Mi empresa pone su propio operador').check();
    await page.getByLabel('Que lo entregue CHRISCO en mi obra').check();
    await page.getByLabel('Notas para ventas (opcional)').fill('Entrar por el portón sur');
    await page.getByRole('button', { name: 'Revisar solicitud' }).click();

    // Revisión: está libre y se muestran los requisitos de ESTA modalidad.
    await expect(page.getByRole('status')).toContainText('Está libre en esas fechas');
    await expect(page.locator('li', { hasText: 'Contrato de renta firmado' })).toBeVisible();
    await expect(page.locator('li', { hasText: 'Licencia federal vigente del operador' })).toBeVisible();
    await expect(page.locator('li', { hasText: 'Flete en lowboy a tu obra' })).toBeVisible();
    await expect(page.locator('li', { hasText: 'Lowboy y tractocamión propios' })).toHaveCount(0);
    await expect(page.locator('li', { hasText: 'Operador de CHRISCO' })).toHaveCount(0);

    await page.getByRole('button', { name: 'Confirmar y reservar' }).click();
    await expect(page.getByRole('status')).toContainText('Solicitud CHR-');
    folio = (await page.getByRole('status').first().locator('b').textContent())!.trim();
    expect(folio).toMatch(/^CHR-\d{4}-\d{5}$/);

    await expect(page.getByText(/Reservado por/)).toContainText(/\d\d:\d\d/);
    const mensaje = page.getByLabel('Mensaje para ventas');
    await expect(mensaje).toHaveValue(new RegExp(folio));
    await expect(mensaje).toHaveValue(/Renta Alfa \(REN-A\)/);
    await expect(mensaje).toHaveValue(new RegExp(DESTINO));
    await expect(mensaje).toHaveValue(/Entrar por el portón sur/);

    const whatsapp = page.getByRole('link', { name: 'Enviar por WhatsApp' });
    const href = (await whatsapp.getAttribute('href'))!;
    expect(href.startsWith('https://wa.me/5217221234567?text=')).toBe(true);
    expect(decodeURIComponent(href)).toContain(folio);
    await expect(whatsapp).toHaveAttribute('target', '_blank');
    await expect(whatsapp).toHaveAttribute('rel', /noopener/);
    await logout(page);
  });

  test('mientras está reservado, otra empresa no puede pedir el mismo equipo', async ({ page }) => {
    await signIn(page, C2.email, C2.password);
    await page.goto('/cliente/catalogo');
    await page.getByLabel('Buscar').fill('Renta Alfa');
    await expect(page.getByRole('heading', { name: 'Catálogo de maquinaria (1)' })).toBeVisible();
    await page.getByRole('link', { name: /Renta Alfa/ }).click();

    await expect(page.getByText(/Ocupado del/)).toHaveCount(1); // la ficha muestra la reserva
    await page.getByLabel('Lugar donde se usará *').fill('Otra obra en Toluca');
    await page.getByRole('button', { name: 'Revisar solicitud' }).click();
    await expect(page.getByRole('alert')).toContainText('ya no está libre en esas fechas');
    await expect(page.getByRole('button', { name: 'Confirmar y reservar' })).toBeDisabled();
    await logout(page);
  });

  test('«Mis rentas» muestra la solicitud con su cuenta regresiva y su mensaje', async ({
    page,
  }) => {
    await signIn(page, C1.email, C1.password);
    await page.getByRole('link', { name: 'Mis rentas' }).click();
    await expect(page.getByRole('heading', { name: 'Mis rentas (1)' })).toBeVisible();
    const fila = page.getByRole('row').filter({ hasText: folio });
    await expect(fila).toContainText('Renta Alfa');
    await expect(fila).toContainText('Solicitada');

    await fila.getByRole('link', { name: 'Ver' }).click();
    await expect(page.getByRole('heading', { name: folio })).toBeVisible();
    await expect(page.getByText(/Equipo reservado/)).toContainText(/\d\d:\d\d/);
    await expect(page.locator('dd', { hasText: DESTINO })).toBeVisible();
    await expect(page.getByText('Lo recoge el cliente')).toHaveCount(0);
    await expect(page.locator('dd', { hasText: 'Entrega CHRISCO en la obra' })).toBeVisible();
    await expect(page.locator('li', { hasText: 'Licencia federal vigente del operador' })).toBeVisible();
    await expect(page.getByLabel('Mensaje para ventas')).toHaveValue(new RegExp(folio));
    await logout(page);
  });

  test('el personal ve las rentas de todas las empresas, sin los botones del cliente', async ({
    page,
  }) => {
    await signIn(page, VENTAS.email, VENTAS.password);
    await page.getByRole('link', { name: 'Rentas' }).click();
    await expect(page.getByRole('heading', { name: 'Rentas (1)' })).toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: folio })).toContainText(C1.razonSocial);

    await page.getByLabel('Buscar').fill('empresa que no existe');
    await expect(page.getByText('No hay rentas con esos filtros.')).toBeVisible();
    await page.getByLabel('Buscar').fill('Constructora Uno');
    await expect(page.getByRole('row').filter({ hasText: folio })).toBeVisible();
    await page.getByLabel('Estado').selectOption('cancelada');
    await expect(page.getByText('No hay rentas con esos filtros.')).toBeVisible();
    await page.getByLabel('Estado').selectOption('solicitada');

    await page.getByRole('row').filter({ hasText: folio }).getByRole('link', { name: 'Ver' }).click();
    await expect(page.getByRole('heading', { name: folio })).toBeVisible();
    await expect(page.getByText(C1.razonSocial)).toBeVisible();
    await expect(page.getByText('Documentos', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Mensaje para ventas')).toHaveCount(0); // eso es para el cliente
    await logout(page);
  });

  test('un cliente no ve las rentas de otra empresa', async ({ page }) => {
    await signIn(page, C2.email, C2.password);
    await page.goto('/cliente/rentas');
    await expect(page.getByRole('heading', { name: 'Mis rentas (0)' })).toBeVisible();
    await expect(page.getByText(folio)).toHaveCount(0);
    await logout(page);
  });

  test('cancelar la solicitud libera el equipo al instante', async ({ page, browser }) => {
    await signIn(page, C1.email, C1.password);
    await page.goto('/cliente/rentas');
    await page.getByRole('row').filter({ hasText: folio }).getByRole('link', { name: 'Ver' }).click();
    await page.getByRole('button', { name: 'Cancelar solicitud' }).click();
    await page.getByRole('button', { name: 'Sí, cancelar' }).click();
    await expect(page.locator('app-status-badge').getByText('Cancelada')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Cancelar solicitud' })).toHaveCount(0);

    // La otra empresa ya puede pedir el equipo para las mismas fechas.
    const dos = await (await browser.newContext()).newPage();
    await signIn(dos, C2.email, C2.password);
    await dos.goto('/cliente/catalogo');
    await dos.getByLabel('Buscar').fill('Renta Alfa');
    await expect(dos.getByRole('heading', { name: 'Catálogo de maquinaria (1)' })).toBeVisible();
    await dos.getByRole('link', { name: /Renta Alfa/ }).click();
    await dos.getByLabel('Lugar donde se usará *').fill('Obra de la empresa dos');
    await dos.getByRole('button', { name: 'Revisar solicitud' }).click();
    await expect(dos.getByRole('status')).toContainText('Está libre en esas fechas');
    await dos.getByRole('button', { name: 'Confirmar y reservar' }).click();
    await expect(dos.getByRole('status')).toContainText('Solicitud CHR-');
  });

  test('una empresa no puede tener más de 3 solicitudes abiertas', async ({ page, request }) => {
    // La empresa uno ya canceló la suya: abre 3 por la API...
    const headers = await userHeaders(request, C1.email, C1.password);
    const equipos = await (await request.get('/api/equipos?limit=100', { headers })).json();
    const porNombre = (n: string) => equipos.items.find((e: { nombre: string }) => e.nombre === n).id;
    for (const [i, nombre] of ['Renta Beta', 'Renta Gamma', 'Renta Delta'].entries()) {
      const res = await request.post('/api/rentas/solicitudes', {
        headers,
        data: {
          equipo_id: porNombre(nombre),
          desde: new Date(Date.now() + (48 + i * 24) * 3600_000).toISOString(),
          hasta: new Date(Date.now() + (56 + i * 24) * 3600_000).toISOString(),
          destino: 'Obra de prueba del límite',
          operador_modo: 'chrisco',
          transporte: 'recoge',
        },
      });
      expect(res.status(), await res.text()).toBe(201);
    }

    // ...y la cuarta, por la pantalla, se rechaza con un mensaje claro.
    await signIn(page, C1.email, C1.password);
    await page.goto('/cliente/catalogo');
    await page.getByLabel('Buscar').fill('Épsilon');
    await expect(page.getByRole('heading', { name: 'Catálogo de maquinaria (1)' })).toBeVisible();
    await page.getByRole('link', { name: /Épsilon/ }).click();
    await page.getByLabel('Lugar donde se usará *').fill('Cuarta obra');
    await page.getByRole('button', { name: 'Revisar solicitud' }).click();
    await page.getByRole('button', { name: 'Confirmar y reservar' }).click();
    await expect(page.getByRole('alert')).toContainText('3 solicitudes abiertas');
  });
});
