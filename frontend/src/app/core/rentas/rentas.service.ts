import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  Cobranza,
  Cotizacion,
  CotizacionCalculo,
  Cumplimiento,
  Documento,
  Movimiento,
  Movimientos,
  MovimientoTipo,
  Pago,
  CotizacionInput,
  CotizacionSugerida,
  Page,
  Renta,
  RentaEstado,
  SolicitudCreada,
  SolicitudIn,
  SolicitudPreview,
  Whatsapp,
} from '../api/models';
import { API_URL } from '../auth/auth.service';
import { toParams } from '../catalogo/catalogo.service';

export interface RentasFiltros {
  estado?: RentaEstado;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface CobranzaFiltros extends RentasFiltros {
  solo_con_saldo?: boolean;
}

/** Solicitudes de renta: el cliente ve las de su empresa; el personal, todas. */
@Injectable({ providedIn: 'root' })
export class RentasService {
  private readonly http = inject(HttpClient);
  private readonly base = `${API_URL}/rentas`;

  /** Qué se le pedirá al cliente y si el equipo está libre; no reserva nada. */
  preview(body: SolicitudIn): Observable<SolicitudPreview> {
    return this.http.post<SolicitudPreview>(`${this.base}/solicitudes/preview`, body);
  }

  /** Reserva el equipo 20 minutos y devuelve el mensaje para ventas. */
  create(body: SolicitudIn): Observable<SolicitudCreada> {
    return this.http.post<SolicitudCreada>(`${this.base}/solicitudes`, body);
  }

  list(filtros: RentasFiltros): Observable<Page<Renta>> {
    return this.http.get<Page<Renta>>(this.base, { params: toParams(filtros) });
  }

  get(id: string): Observable<Renta> {
    return this.http.get<Renta>(`${this.base}/${id}`);
  }

  whatsapp(id: string): Observable<Whatsapp> {
    return this.http.get<Whatsapp>(`${this.base}/${id}/whatsapp`);
  }

  /** La cotización viva de la renta; 404 si aún no tiene. */
  cotizacion(id: string): Observable<Cotizacion> {
    return this.http.get<Cotizacion>(`${this.base}/${id}/cotizacion`);
  }

  sugerida(id: string): Observable<CotizacionSugerida> {
    return this.http.get<CotizacionSugerida>(`${this.base}/${id}/cotizacion/sugerida`);
  }

  /** Totales con la misma aritmética que al guardar (el servidor es la única fuente). */
  calcular(id: string, body: CotizacionInput): Observable<CotizacionCalculo> {
    return this.http.post<CotizacionCalculo>(`${this.base}/${id}/cotizacion/calcular`, body);
  }

  cotizar(id: string, body: CotizacionInput): Observable<Cotizacion> {
    return this.http.post<Cotizacion>(`${this.base}/${id}/cotizacion`, body);
  }

  aceptar(id: string): Observable<Renta> {
    return this.http.post<Renta>(`${this.base}/${id}/cotizacion/aceptar`, {});
  }

  rechazarCotizacion(id: string): Observable<Renta> {
    return this.http.post<Renta>(`${this.base}/${id}/cotizacion/rechazar`, {});
  }

  /** Ventas no puede atender la solicitud. */
  rechazarSolicitud(id: string, motivo: string): Observable<Renta> {
    return this.http.post<Renta>(`${this.base}/${id}/rechazar`, { motivo });
  }

  cancel(id: string): Observable<Renta> {
    return this.http.post<Renta>(`${this.base}/${id}/cancelar`, {});
  }

  // ------------------------------------------------------------ cumplimiento del apartado

  cumplimiento(id: string): Observable<Cumplimiento> {
    return this.http.get<Cumplimiento>(`${this.base}/${id}/cumplimiento`);
  }

  subirDocumento(id: string, requisito: string, archivo: File): Observable<Documento> {
    const body = new FormData();
    body.append('requisito', requisito);
    body.append('archivo', archivo);
    return this.http.post<Documento>(`${this.base}/${id}/documentos`, body);
  }

  reportarPago(
    id: string,
    campos: { monto: number; fecha_pago: string; referencia: string },
    comprobante: File,
  ): Observable<Pago> {
    const body = new FormData();
    body.append('monto', String(campos.monto));
    body.append('fecha_pago', campos.fecha_pago);
    if (campos.referencia) body.append('referencia', campos.referencia);
    body.append('comprobante', comprobante);
    return this.http.post<Pago>(`${this.base}/${id}/pagos`, body);
  }

  /** Los archivos son privados: se bajan con la sesión y se abren desde memoria. */
  documento(id: string, docId: string): Observable<Blob> {
    return this.http.get(`${this.base}/${id}/documentos/${docId}/archivo`, {
      responseType: 'blob',
    });
  }

  comprobante(id: string, pagoId: string): Observable<Blob> {
    return this.http.get(`${this.base}/${id}/pagos/${pagoId}/comprobante`, {
      responseType: 'blob',
    });
  }

  /** `licencia` solo al aprobar una licencia: lo que el personal leyó de la foto. */
  revisarDocumento(
    id: string,
    docId: string,
    aprobado: boolean,
    nota?: string,
    licencia?: { numero: string; vigente_hasta: string },
  ) {
    return this.http.post<Cumplimiento>(`${this.base}/${id}/documentos/${docId}/revisar`, {
      aprobado,
      nota: nota ?? null,
      ...licencia,
    });
  }

  revisarPago(id: string, pagoId: string, aprobado: boolean, nota?: string) {
    return this.http.post<Cumplimiento>(`${this.base}/${id}/pagos/${pagoId}/revisar`, {
      aprobado,
      nota: nota ?? null,
    });
  }

  marcarCondicion(id: string, codigo: string, cumplida: boolean): Observable<Cumplimiento> {
    return this.http.post<Cumplimiento>(`${this.base}/${id}/condiciones/${codigo}`, { cumplida });
  }

  // ------------------------------------------------------------ salida y regreso del equipo

  movimientos(id: string): Observable<Movimientos> {
    return this.http.get<Movimientos>(`${this.base}/${id}/movimientos`);
  }

  registrarMovimiento(
    id: string,
    campos: { tipo: MovimientoTipo; horometro: number; notas: string },
    foto: File,
  ): Observable<Movimiento> {
    const body = new FormData();
    body.append('tipo', campos.tipo);
    body.append('horometro', String(campos.horometro));
    if (campos.notas) body.append('notas', campos.notas);
    body.append('foto', foto);
    return this.http.post<Movimiento>(`${this.base}/${id}/movimientos`, body);
  }

  fotoMovimiento(id: string, movimientoId: string): Observable<Blob> {
    return this.http.get(`${this.base}/${id}/movimientos/${movimientoId}/foto`, {
      responseType: 'blob',
    });
  }

  cobranza(filtros: CobranzaFiltros): Observable<Cobranza> {
    return this.http.get<Cobranza>(`${API_URL}/admin/cobranza`, { params: toParams(filtros) });
  }
}
