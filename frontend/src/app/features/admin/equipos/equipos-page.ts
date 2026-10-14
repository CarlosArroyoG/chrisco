import { CurrencyPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { catchError, debounceTime, distinctUntilChanged, of, Subject, switchMap, tap } from 'rxjs';
import { apiErrorMessage } from '../../../core/api/errors';
import { Categoria, Equipo, EquipoStatus } from '../../../core/api/models';
import { AuthService } from '../../../core/auth/auth.service';
import { CatalogoService, fotoUrl } from '../../../core/catalogo/catalogo.service';
import { StatusBadge } from '../../../shared/status-badge/status-badge';
import { EquiposService } from './equipos.service';

const PAGE_SIZE = 25;

/** Lista de equipos con búsqueda, filtros y paginación. */
@Component({
  selector: 'app-equipos-page',
  imports: [CurrencyPipe, ReactiveFormsModule, RouterLink, StatusBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h1 class="text-lg font-black">Equipos ({{ total() }})</h1>
      @if (isAdmin()) {
        <div class="flex gap-2">
          <a routerLink="/admin/equipos/importar" class="btn-secondary">Importar CSV</a>
          <a routerLink="/admin/equipos/nuevo" class="btn-primary">Nuevo equipo</a>
        </div>
      }
    </div>

    <div class="mt-3 grid gap-2 sm:grid-cols-3">
      <input
        type="search"
        [formControl]="q"
        placeholder="Buscar por código, nombre, marca, serie…"
        aria-label="Buscar"
        class="input"
      />
      <select [formControl]="categoria" aria-label="Categoría" class="input">
        <option value="">Todas las categorías</option>
        @for (c of categorias(); track c.id) {
          <option [value]="c.id">{{ c.nombre }}</option>
        }
      </select>
      <select [formControl]="status" aria-label="Estado" class="input">
        <option value="">Todos los estados</option>
        <option value="activo">Activos</option>
        <option value="mantenimiento">En mantenimiento</option>
        <option value="baja">Baja</option>
      </select>
    </div>

    @if (error()) {
      <p role="alert" class="alert-error mt-3">{{ error() }}</p>
    }

    <div class="mt-3 overflow-x-auto rounded-xl border bg-white">
      <table class="w-full text-left text-xs">
        <thead class="bg-chrisco-charcoal text-[10px] font-bold text-white uppercase">
          <tr>
            <th class="p-3"></th>
            <th class="p-3">Código</th>
            <th class="p-3">Equipo</th>
            <th class="p-3">Categoría</th>
            <th class="p-3">Tarifa</th>
            <th class="p-3">Situación</th>
            <th class="p-3"></th>
          </tr>
        </thead>
        <tbody class="divide-y">
          @for (e of items(); track e.id) {
            <tr>
              <td class="p-2">
                @if (e.fotos.length) {
                  <img
                    [src]="fotoUrl(e.fotos[0].id, 'thumb')"
                    alt=""
                    class="size-12 rounded object-cover"
                  />
                } @else {
                  <div class="size-12 rounded bg-slate-100"></div>
                }
              </td>
              <td class="p-3 font-mono font-bold">{{ e.codigo }}</td>
              <td class="p-3">
                <span class="font-semibold">{{ e.nombre }}</span
                ><br />
                <span class="text-slate-500"
                  >{{ e.marca }} {{ e.modelo }} · {{ e.numero_serie }}</span
                >
              </td>
              <td class="p-3">{{ e.categoria_nombre }}</td>
              <td class="p-3">
                @if (e.tarifa_hora) {
                  {{ e.tarifa_hora | currency: 'MXN' : 'symbol-narrow' : '1.0-2' }}/h
                }
                @if (e.tarifa_hora && e.tarifa_dia) {
                  <br />
                }
                @if (e.tarifa_dia) {
                  {{ e.tarifa_dia | currency: 'MXN' : 'symbol-narrow' : '1.0-2' }}/día
                }
              </td>
              <td class="p-3"><app-status-badge [status]="e.estado_actual" /></td>
              <td class="p-3">
                <a [routerLink]="['/admin/equipos', e.id]" class="link">{{
                  isAdmin() ? 'Editar' : 'Ver'
                }}</a>
              </td>
            </tr>
          } @empty {
            <tr>
              <td colspan="7" class="p-6 text-center text-slate-500">
                {{ loaded() ? 'No hay equipos con esos filtros.' : 'Cargando…' }}
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>

    @if (pages() > 1) {
      <nav class="mt-3 flex items-center justify-between text-xs" aria-label="Paginación">
        <button
          type="button"
          class="btn-secondary"
          [disabled]="page() === 0"
          (click)="go(page() - 1)"
        >
          Anterior
        </button>
        <span>Página {{ page() + 1 }} de {{ pages() }}</span>
        <button
          type="button"
          class="btn-secondary"
          [disabled]="page() + 1 >= pages()"
          (click)="go(page() + 1)"
        >
          Siguiente
        </button>
      </nav>
    }
  `,
})
export class EquiposPage implements OnInit {
  private readonly service = inject(EquiposService);
  private readonly catalogo = inject(CatalogoService);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly fotoUrl = fotoUrl;
  protected readonly q = new FormControl('', { nonNullable: true });
  protected readonly categoria = new FormControl('', { nonNullable: true });
  protected readonly status = new FormControl<'' | EquipoStatus>('', { nonNullable: true });

  protected readonly categorias = signal<Categoria[]>([]);
  protected readonly items = signal<Equipo[]>([]);
  protected readonly total = signal(0);
  protected readonly page = signal(0);
  protected readonly loaded = signal(false);
  protected readonly error = signal<string | null>(null);
  /** Cada consulta cancela a la anterior: una respuesta vieja no pisa a la nueva. */
  private readonly load$ = new Subject<number>();
  protected readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / PAGE_SIZE)));
  protected readonly isAdmin = computed(() => this.auth.user()?.role === 'admin');

  ngOnInit(): void {
    this.load$
      .pipe(
        tap((page) => {
          this.page.set(page);
          this.loaded.set(false);
          this.error.set(null);
        }),
        switchMap((page) =>
          this.service
            .list({
              q: this.q.value.trim(),
              categoria_id: this.categoria.value,
              status_filter: this.status.value || undefined,
              limit: PAGE_SIZE,
              offset: page * PAGE_SIZE,
            })
            .pipe(
              catchError((err: unknown) => {
                this.error.set(apiErrorMessage(err, 'No se pudo cargar la lista de equipos.'));
                return of(null);
              }),
            ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        if (result) {
          this.items.set(result.items);
          this.total.set(result.total);
        }
        this.loaded.set(true);
      });

    this.catalogo.categorias().subscribe((categorias) => this.categorias.set(categorias));
    // Cualquier cambio de filtro regresa a la primera página.
    this.q.valueChanges
      .pipe(debounceTime(300), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.go(0));
    this.categoria.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.go(0));
    this.status.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => this.go(0));
    this.go(0);
  }

  protected go(page: number): void {
    this.load$.next(page);
  }
}
