import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  Bloqueo,
  BloqueoIn,
  Equipo,
  EquipoInput,
  EquipoStatus,
  Foto,
  ImportResult,
  Page,
} from '../../../core/api/models';
import { API_URL } from '../../../core/auth/auth.service';
import { toParams } from '../../../core/catalogo/catalogo.service';

export interface EquiposFiltros {
  q?: string;
  categoria_id?: string;
  status_filter?: EquipoStatus;
  limit?: number;
  offset?: number;
}

/** API de registro de equipos (personal de CHRISCO). */
@Injectable({ providedIn: 'root' })
export class EquiposService {
  private readonly http = inject(HttpClient);
  private readonly base = `${API_URL}/admin/equipos`;

  list(filtros: EquiposFiltros): Observable<Page<Equipo>> {
    return this.http.get<Page<Equipo>>(this.base, { params: toParams(filtros) });
  }

  get(id: string): Observable<Equipo> {
    return this.http.get<Equipo>(`${this.base}/${id}`);
  }

  create(body: EquipoInput): Observable<Equipo> {
    return this.http.post<Equipo>(this.base, body);
  }

  update(id: string, body: EquipoInput): Observable<Equipo> {
    return this.http.put<Equipo>(`${this.base}/${id}`, body);
  }

  addFoto(id: string, file: File): Observable<Foto> {
    const body = new FormData();
    body.append('foto', file);
    return this.http.post<Foto>(`${this.base}/${id}/fotos`, body);
  }

  removeFoto(id: string, fotoId: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}/fotos/${fotoId}`);
  }

  bloqueos(id: string): Observable<Bloqueo[]> {
    return this.http.get<Bloqueo[]>(`${this.base}/${id}/bloqueos`);
  }

  createBloqueo(id: string, body: BloqueoIn): Observable<Bloqueo> {
    return this.http.post<Bloqueo>(`${this.base}/${id}/bloqueos`, body);
  }

  releaseBloqueo(bloqueoId: string): Observable<void> {
    return this.http.post<void>(`${API_URL}/admin/bloqueos/${bloqueoId}/liberar`, {});
  }

  /** Con `dryRun` solo valida el archivo y reporta errores por fila; no guarda nada. */
  importCsv(file: File, dryRun: boolean): Observable<ImportResult> {
    const body = new FormData();
    body.append('archivo', file);
    return this.http.post<ImportResult>(`${this.base}/importar`, body, {
      params: toParams({ dry_run: dryRun }),
    });
  }

  template(categoriaId?: string): Observable<Blob> {
    return this.http.get(`${this.base}/importar/plantilla`, {
      params: toParams({ categoria_id: categoriaId }),
      responseType: 'blob',
    });
  }
}
