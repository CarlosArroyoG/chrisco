import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { EmpresaDetail, EmpresaListItem, EmpresaStatus } from '../../core/api/models';
import { API_URL } from '../../core/auth/auth.service';

/** API de revisión de empresas para el personal de CHRISCO. */
@Injectable({ providedIn: 'root' })
export class AdminEmpresasService {
  private readonly http = inject(HttpClient);
  private readonly base = `${API_URL}/admin/empresas`;

  list(status?: EmpresaStatus): Observable<EmpresaListItem[]> {
    const params = status ? new HttpParams().set('status_filter', status) : undefined;
    return this.http.get<EmpresaListItem[]>(this.base, { params });
  }

  get(id: string): Observable<EmpresaDetail> {
    return this.http.get<EmpresaDetail>(`${this.base}/${id}`);
  }

  /** La constancia es privada: se baja con la sesión y se abre desde memoria. */
  constancia(id: string): Observable<Blob> {
    return this.http.get(`${this.base}/${id}/constancia`, { responseType: 'blob' });
  }

  approve(id: string): Observable<void> {
    return this.http.post<void>(`${this.base}/${id}/aprobar`, {});
  }

  reject(id: string, motivo: string): Observable<void> {
    return this.http.post<void>(`${this.base}/${id}/rechazar`, { motivo });
  }
}
