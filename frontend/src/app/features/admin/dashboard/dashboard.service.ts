import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Dashboard } from '../../../core/api/models';
import { API_URL } from '../../../core/auth/auth.service';

/** Cifras del panel del administrador. */
@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);

  get(): Observable<Dashboard> {
    return this.http.get<Dashboard>(`${API_URL}/admin/dashboard`);
  }
}
