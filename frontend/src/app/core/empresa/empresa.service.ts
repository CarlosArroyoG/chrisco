import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { CompanyUser, EmpresaDetail } from '../api/models';
import { toFormData } from '../api/form-data';
import { API_URL } from '../auth/auth.service';

export interface CompanyFields {
  razon_social: string;
  sitio_web: string;
  rfc: string;
}

export interface RegistroFields extends CompanyFields {
  full_name: string;
  email: string;
  password: string;
}

/** API de la empresa cliente: registro público, su estado y su equipo de usuarios. */
@Injectable({ providedIn: 'root' })
export class EmpresaService {
  private readonly http = inject(HttpClient);

  register(fields: RegistroFields, constancia: File): Observable<{ detail: string }> {
    return this.http.post<{ detail: string }>(
      `${API_URL}/empresa/registro`,
      toFormData({ ...fields }, constancia),
    );
  }

  mine(): Observable<EmpresaDetail> {
    return this.http.get<EmpresaDetail>(`${API_URL}/empresa/me`);
  }

  resubmit(fields: CompanyFields, constancia: File): Observable<EmpresaDetail> {
    return this.http.put<EmpresaDetail>(
      `${API_URL}/empresa/me`,
      toFormData({ ...fields }, constancia),
    );
  }

  inviteUser(email: string, full_name: string): Observable<CompanyUser> {
    return this.http.post<CompanyUser>(`${API_URL}/empresa/me/usuarios`, { email, full_name });
  }

  removeUser(userId: string): Observable<void> {
    return this.http.delete<void>(`${API_URL}/empresa/me/usuarios/${userId}`);
  }
}
