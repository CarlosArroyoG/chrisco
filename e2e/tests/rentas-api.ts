import { APIRequestContext, expect } from '@playwright/test';

/** Ayudantes para preparar rentas por la API (las pruebas de interfaz parten de ahí). */

type Headers = { Authorization: string };

/** Id de un equipo del catálogo por su código, consultando como cliente. */
export async function equipoId(
  request: APIRequestContext,
  headers: Headers,
  codigo: string,
): Promise<string> {
  const res = await request.get(`/api/equipos?q=${encodeURIComponent(codigo)}`, { headers });
  const item = (await res.json()).items.find((e: { codigo: string }) => e.codigo === codigo);
  expect(item, `el equipo ${codigo} debe estar en el catálogo`).toBeTruthy();
  return item.id;
}

/** Mañana de 08:00 a 18:00 (hora local) como instantes ISO: el periodo por defecto de las pruebas. */
export function tomorrowWorkday(): { desde: string; hasta: string } {
  const start = new Date();
  start.setDate(start.getDate() + 1);
  start.setHours(8, 0, 0, 0);
  return {
    desde: start.toISOString(),
    hasta: new Date(start.getTime() + 10 * 3600_000).toISOString(),
  };
}

/** Solicitud de renta hecha por un cliente por la API. Devuelve la renta creada. */
export async function solicitarPorApi(
  request: APIRequestContext,
  headers: Headers,
  equipo: string,
  extra: Record<string, unknown> = {},
): Promise<{ id: string; folio: string }> {
  const res = await request.post('/api/rentas/solicitudes', {
    headers,
    data: {
      equipo_id: equipo,
      ...tomorrowWorkday(),
      destino: 'Autopista Morelia - Guadalajara km 45',
      operador_modo: 'chrisco',
      transporte: 'entrega',
      ...extra,
    },
  });
  expect(res.status(), await res.text()).toBe(201);
  return res.json();
}
