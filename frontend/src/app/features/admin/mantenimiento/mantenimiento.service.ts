import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  MantenimientoAtencion,
  PlanInput,
  PlanMantenimiento,
  RegistroMantenimiento,
} from '../../../core/api/models';
import { API_URL } from '../../../core/auth/auth.service';

/** Planes de mantenimiento periódico de los equipos (ver: personal; cambiar: admin). */
@Injectable({ providedIn: 'root' })
export class MantenimientoService {
  private readonly http = inject(HttpClient);
  private readonly base = `${API_URL}/admin/mantenimiento`;

  /** Planes de todos los equipos, los más urgentes primero. */
  atencion(soloAtencion: boolean): Observable<MantenimientoAtencion[]> {
    return this.http.get<MantenimientoAtencion[]>(this.base, {
      params: { solo_atencion: soloAtencion },
    });
  }

  planes(equipoId: string): Observable<PlanMantenimiento[]> {
    return this.http.get<PlanMantenimiento[]>(`${API_URL}/admin/equipos/${equipoId}/mantenimiento`);
  }

  crear(equipoId: string, body: PlanInput): Observable<PlanMantenimiento> {
    return this.http.post<PlanMantenimiento>(
      `${API_URL}/admin/equipos/${equipoId}/mantenimiento`,
      body,
    );
  }

  borrar(planId: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${planId}`);
  }

  /** El servicio se hizo: sin fecha ni horómetro se toman los de hoy y los del equipo. */
  realizado(
    planId: string,
    body: { horometro?: number; notas?: string },
  ): Observable<RegistroMantenimiento> {
    return this.http.post<RegistroMantenimiento>(`${this.base}/${planId}/realizado`, body);
  }

  registros(planId: string): Observable<RegistroMantenimiento[]> {
    return this.http.get<RegistroMantenimiento[]>(`${this.base}/${planId}/registros`);
  }
}
