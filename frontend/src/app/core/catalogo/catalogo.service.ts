import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Categoria, Disponibilidad, EquipoCatalogo, Page } from '../api/models';
import { API_URL } from '../auth/auth.service';

export interface CatalogoFiltros {
  q?: string;
  categoria_id?: string;
  /** Con `desde` y `hasta` cada equipo indica si está libre en ese periodo. */
  desde?: string;
  hasta?: string;
  solo_disponibles?: boolean;
  /** Solo los equipos que están así ahora mismo (libre, rentado…). */
  situacion?: string;
  limit?: number;
  offset?: number;
}

/** URL de una foto de equipo. Las fotos del catálogo son abiertas, así que sirve en un `<img>`. */
export function fotoUrl(fotoId: string, size: 'thumb' | 'full'): string {
  return `${API_URL}/equipos/fotos/${fotoId}/${size}`;
}

/** Arma los parámetros de consulta omitiendo los que vienen vacíos. */
export function toParams(filtros: object): HttpParams {
  let params = new HttpParams();
  for (const [key, value] of Object.entries(filtros)) {
    if (value !== undefined && value !== null && value !== '')
      params = params.set(key, String(value));
  }
  return params;
}

/** Catálogo de maquinaria para clientes aprobados y personal. */
@Injectable({ providedIn: 'root' })
export class CatalogoService {
  private readonly http = inject(HttpClient);

  list(filtros: CatalogoFiltros): Observable<Page<EquipoCatalogo>> {
    return this.http.get<Page<EquipoCatalogo>>(`${API_URL}/equipos`, { params: toParams(filtros) });
  }

  get(id: string): Observable<EquipoCatalogo> {
    return this.http.get<EquipoCatalogo>(`${API_URL}/equipos/${id}`);
  }

  disponibilidad(id: string, desde: string, hasta: string): Observable<Disponibilidad> {
    return this.http.get<Disponibilidad>(`${API_URL}/equipos/${id}/disponibilidad`, {
      params: toParams({ desde, hasta }),
    });
  }

  categorias(): Observable<Categoria[]> {
    return this.http.get<Categoria[]>(`${API_URL}/categorias`);
  }
}
