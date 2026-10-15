import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Personal, PersonalInput, PersonalUpdate } from '../../../core/api/models';
import { API_URL } from '../../../core/auth/auth.service';

/** Personal de CHRISCO (admin, ventas, operador): solo lo gestionan los administradores. */
@Injectable({ providedIn: 'root' })
export class PersonalService {
  private readonly http = inject(HttpClient);
  private readonly base = `${API_URL}/admin/personal`;

  list(): Observable<Personal[]> {
    return this.http.get<Personal[]>(this.base);
  }

  create(body: PersonalInput): Observable<Personal> {
    return this.http.post<Personal>(this.base, body);
  }

  update(id: string, body: PersonalUpdate): Observable<Personal> {
    return this.http.put<Personal>(`${this.base}/${id}`, body);
  }

  resendInvitation(id: string): Observable<void> {
    return this.http.post<void>(`${this.base}/${id}/invitacion`, {});
  }
}
