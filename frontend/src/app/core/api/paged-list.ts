import { DestroyRef, Signal, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Observable, Subject, catchError, of, switchMap, tap } from 'rxjs';
import { apiErrorMessage } from './errors';
import { Page } from './models';

export interface PagedList<T> {
  items: Signal<T[]>;
  total: Signal<number>;
  page: Signal<number>;
  pages: Signal<number>;
  loaded: Signal<boolean>;
  error: Signal<string | null>;
  /** Pide una página. Cada petición cancela a la anterior: una respuesta vieja no pisa a la nueva. */
  go: (page: number) => void;
}

/**
 * Lista paginada con filtros. Se crea en el contexto de inyección de un componente (campo de la
 * clase). Quien la usa llama a `go(0)` al arrancar y cada vez que cambia un filtro.
 */
export function pagedList<T>(options: {
  pageSize: number;
  fetch: (page: number) => Observable<Page<T>>;
  errorMessage: string;
}): PagedList<T> {
  const items = signal<T[]>([]);
  const total = signal(0);
  const page = signal(0);
  const loaded = signal(false);
  const error = signal<string | null>(null);
  const requests = new Subject<number>();

  requests
    .pipe(
      tap((requested) => {
        page.set(requested);
        loaded.set(false);
        error.set(null);
      }),
      switchMap((requested) =>
        options.fetch(requested).pipe(
          catchError((err: unknown) => {
            error.set(apiErrorMessage(err, options.errorMessage));
            return of(null);
          }),
        ),
      ),
      takeUntilDestroyed(inject(DestroyRef)),
    )
    .subscribe((result) => {
      if (result) {
        items.set(result.items);
        total.set(result.total);
      }
      loaded.set(true);
    });

  return {
    items,
    total,
    page,
    pages: computed(() => Math.max(1, Math.ceil(total() / options.pageSize))),
    loaded,
    error,
    go: (requested) => requests.next(requested),
  };
}
