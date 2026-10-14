import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Categoria, CategoriaAdmin, CategoriaIn } from '../../../core/api/models';
import { API_URL } from '../../../core/auth/auth.service';

/** API de categorías de maquinaria (gestión del personal). */
@Injectable({ providedIn: 'root' })
export class CategoriasService {
  private readonly http = inject(HttpClient);
  private readonly base = `${API_URL}/admin/categorias`;

  list(): Observable<CategoriaAdmin[]> {
    return this.http.get<CategoriaAdmin[]>(this.base);
  }

  create(body: CategoriaIn): Observable<Categoria> {
    return this.http.post<Categoria>(this.base, body);
  }

  update(id: string, body: CategoriaIn): Observable<Categoria> {
    return this.http.put<Categoria>(`${this.base}/${id}`, body);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }
}
