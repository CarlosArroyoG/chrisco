import { describe, expect, it } from 'vitest';
import { ESTADOS_ABIERTOS, ETAPAS, TONO_CLASES } from './etapas';

describe('etapas de una renta', () => {
  it('toda etapa tiene sus textos y un tono con colores', () => {
    for (const [estado, etapa] of Object.entries(ETAPAS)) {
      expect(etapa.etiqueta, estado).not.toBe('');
      expect(etapa.accion, estado).not.toBe('');
      expect(etapa.pista, estado).not.toBe('');
      expect(TONO_CLASES[etapa.tono], estado).toBeTruthy();
    }
  });

  it('las etapas abiertas existen y las que ya terminaron no están entre ellas', () => {
    for (const estado of ESTADOS_ABIERTOS) expect(ETAPAS[estado]).toBeDefined();
    for (const cerrada of ['devuelta', 'cerrada', 'vencida', 'cancelada', 'rechazada'] as const) {
      expect(ESTADOS_ABIERTOS).not.toContain(cerrada);
    }
  });

  it('el botón de cada etapa abierta dice qué hacer ahora', () => {
    expect(ETAPAS.solicitada.accion).toBe('Ver mi solicitud');
    expect(ETAPAS.cotizada.accion).toBe('Revisar cotización');
    expect(ETAPAS.apartada.accion).toBe('Completar requisitos y pagar');
    expect(ETAPAS.confirmada.accion).toBe('Ver mi renta');
    expect(ETAPAS.en_renta.accion).toBe('Ver mi renta');
  });
});
