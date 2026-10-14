import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
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

  cancel(id: string): Observable<Renta> {
    return this.http.post<Renta>(`${this.base}/${id}/cancelar`, {});
  }
}
