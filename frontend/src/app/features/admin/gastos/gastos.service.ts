import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Gasto, GastoInput, Gastos, GastoCategoria } from '../../../core/api/models';
import { API_URL } from '../../../core/auth/auth.service';
import { toParams } from '../../../core/catalogo/catalogo.service';

export interface GastosFiltros {
  mes?: string;
  categoria?: GastoCategoria;
  limit?: number;
  offset?: number;
}

/** Gastos del negocio (ver: personal; registrar y borrar: administradores). */
@Injectable({ providedIn: 'root' })
export class GastosService {
  private readonly http = inject(HttpClient);
  private readonly base = `${API_URL}/admin/gastos`;

  list(filtros: GastosFiltros): Observable<Gastos> {
    return this.http.get<Gastos>(this.base, { params: toParams(filtros) });
  }

  create(body: GastoInput): Observable<Gasto> {
    return this.http.post<Gasto>(this.base, body);
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }
}
