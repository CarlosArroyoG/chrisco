import { APIRequestContext, expect } from '@playwright/test';
import { PDF } from './helpers';

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

/**
 * Lleva una solicitud hasta `apartada`: ventas cotiza 10 h × $1,000 (total $11,600, anticipo
 * $3,480) y el cliente acepta.
 */
export async function apartarPorApi(
  request: APIRequestContext,
  cliente: Headers,
  ventas: Headers,
  equipo: string,
  extra: Record<string, unknown> = {},
): Promise<{ id: string; folio: string }> {
  const renta = await solicitarPorApi(request, cliente, equipo, {
    transporte: 'recoge',
    ...extra,
  });
  const cotizacion = await request.post(`/api/rentas/${renta.id}/cotizacion`, {
    headers: ventas,
    data: {
      partidas: [
        {
          concepto: 'renta',
          descripcion: 'Renta de equipo',
          cantidad: 10,
          unidad: 'hora',
          precio_unitario: 1000,
        },
      ],
    },
  });
  expect(cotizacion.status(), await cotizacion.text()).toBe(201);
  const aceptada = await request.post(`/api/rentas/${renta.id}/cotizacion/aceptar`, {
    headers: cliente,
  });
  expect(aceptada.status(), await aceptada.text()).toBe(200);
  return renta;
}

/**
 * Cumple todo lo que pide una renta apartada con operador de CHRISCO (contrato, póliza y el
 * anticipo de $3,480) y la deja `confirmada`.
 */
export async function confirmarPorApi(
  request: APIRequestContext,
  cliente: Headers,
  ventas: Headers,
  rentaId: string,
): Promise<void> {
  for (const requisito of ['contrato', 'poliza']) {
    const subida = await request.post(`/api/rentas/${rentaId}/documentos`, {
      headers: cliente,
      multipart: { requisito, archivo: PDF },
    });
    expect(subida.status(), await subida.text()).toBe(201);
    const revisada = await request.post(
      `/api/rentas/${rentaId}/documentos/${(await subida.json()).id}/revisar`,
      { headers: ventas, data: { aprobado: true } },
    );
    expect(revisada.status(), await revisada.text()).toBe(200);
  }
  const pago = await request.post(`/api/rentas/${rentaId}/pagos`, {
    headers: cliente,
    multipart: {
      monto: '3480',
      fecha_pago: new Date().toLocaleDateString('en-CA'),
      comprobante: PDF,
    },
  });
  expect(pago.status(), await pago.text()).toBe(201);
  const confirmado = await request.post(
    `/api/rentas/${rentaId}/pagos/${(await pago.json()).id}/revisar`,
    { headers: ventas, data: { aprobado: true } },
  );
  expect(confirmado.status(), await confirmado.text()).toBe(200);
}
