import { CurrencyPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { debounceTime, distinctUntilChanged, merge } from 'rxjs';
import { periodFromInputs } from '../../../core/api/dates';
import { Categoria, EquipoCatalogo } from '../../../core/api/models';
import { pagedList } from '../../../core/api/paged-list';
import { CatalogoFiltros, CatalogoService, fotoUrl } from '../../../core/catalogo/catalogo.service';

const PAGE_SIZE = 12;

/** Catálogo de maquinaria para clientes con empresa aprobada. */
@Component({
  selector: 'app-catalogo-page',
  imports: [CurrencyPipe, ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section
      class="from-chrisco-dark relative overflow-hidden rounded-3xl bg-linear-to-br to-[#2b3a42] px-6 pt-8 pb-14 text-white sm:px-10 sm:pt-10 sm:pb-16"
    >
      <div
        class="bg-chrisco-orange/30 pointer-events-none absolute -top-24 -right-16 size-72 rounded-full blur-3xl"
      ></div>
      <p class="text-chrisco-orange text-xs font-bold tracking-wider uppercase">Catálogo</p>
      <h1 class="mt-1 text-3xl font-extrabold tracking-tight sm:text-4xl">
        Catálogo de maquinaria ({{ list.total() }})
      </h1>
      <p class="mt-2 max-w-xl text-sm text-slate-300">
        Elige el equipo, dinos las fechas y la obra, y lo apartamos mientras te cotizamos.
      </p>
    </section>

    <div class="card -mt-6 relative mx-3 grid gap-3 sm:mx-6 sm:grid-cols-3">
      <input
        type="search"
        [formControl]="q"
        placeholder="Buscar equipo, marca o modelo…"
        aria-label="Buscar"
        class="input sm:col-span-2"
      />
      <select [formControl]="categoria" aria-label="Categoría" class="input">
        <option value="">Todas las categorías</option>
        @for (c of categorias(); track c.id) {
          <option [value]="c.id">{{ c.nombre }}</option>
        }
      </select>

      <div class="grid gap-3 sm:col-span-3 sm:grid-cols-4">
        <div>
          <label for="cat-desde" class="label">Lo necesito desde</label>
          <input id="cat-desde" type="datetime-local" [formControl]="desde" class="input" />
        </div>
        <div>
          <label for="cat-hasta" class="label">Hasta</label>
          <input id="cat-hasta" type="datetime-local" [formControl]="hasta" class="input" />
        </div>
        <label class="flex items-end gap-2 pb-2.5 text-sm font-semibold text-slate-700">
          <input
            type="checkbox"
            [formControl]="soloDisponibles"
            class="accent-chrisco-orange size-4"
          />
          Solo disponibles
        </label>
        @if (rangeHint()) {
          <p class="text-xs text-amber-700 sm:col-span-4">{{ rangeHint() }}</p>
        }
      </div>
    </div>

    @if (list.error()) {
      <p role="alert" class="alert-error mt-3">{{ list.error() }}</p>
    }

    <div class="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
      @for (e of list.items(); track e.id) {
        <a
          [routerLink]="['/cliente/catalogo', e.id]"
          [queryParams]="carryOver()"
          class="card shadow-card hover:shadow-lift group block overflow-hidden !p-0 transition duration-200 hover:-translate-y-1"
        >
          <div class="relative overflow-hidden">
            @if (e.fotos.length) {
              <img
                [src]="fotoUrl(e.fotos[0].id, 'thumb')"
                [alt]="e.nombre"
                class="aspect-[4/3] w-full object-cover transition duration-500 group-hover:scale-105"
                loading="lazy"
              />
            } @else {
              <div
                class="flex aspect-[4/3] items-center justify-center bg-slate-100 text-xs text-slate-400"
              >
                Sin foto
              </div>
            }
            <span
              class="absolute top-3 left-3 rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-bold text-slate-700 shadow-sm backdrop-blur"
              >{{ e.categoria_nombre }}</span
            >
            @if (e.disponible === true) {
              <span
                class="absolute top-3 right-3 rounded-full bg-emerald-500 px-2.5 py-1 text-[11px] font-bold text-white shadow-sm"
                >Disponible en esas fechas</span
              >
            } @else if (e.disponible === false) {
              <span
                class="absolute top-3 right-3 rounded-full bg-rose-500 px-2.5 py-1 text-[11px] font-bold text-white shadow-sm"
                >Ocupado en esas fechas</span
              >
            }
          </div>
          <div class="p-5">
            <h2 class="text-lg font-bold tracking-tight text-slate-900">{{ e.nombre }}</h2>
            <p class="text-sm text-slate-500">
              {{ e.marca }} {{ e.modelo }}
              @if (e.anio) {
                · {{ e.anio }}
              }
            </p>
            <div class="mt-4 flex items-end justify-between gap-3 border-t border-slate-100 pt-4">
              <p class="text-lg font-extrabold text-slate-900">
                @if (e.tarifa_hora) {
                  {{ e.tarifa_hora | currency: 'MXN' : 'symbol-narrow' : '1.0-2' }}/h
                }
                @if (e.tarifa_hora && e.tarifa_dia) {
                  <span class="text-slate-300">·</span>
                }
                @if (e.tarifa_dia) {
                  <span class="text-sm font-semibold text-slate-500"
                    >{{ e.tarifa_dia | currency: 'MXN' : 'symbol-narrow' : '1.0-2' }}/día</span
                  >
                }
              </p>
              <span
                class="text-chrisco-orange-dark text-sm font-semibold transition group-hover:translate-x-0.5"
                >Ver →</span
              >
            </div>
            @if (e.requiere_lowboy) {
              <p class="mt-3 text-[11px] font-semibold text-amber-700">Se entrega en lowboy</p>
            }
          </div>
        </a>
      } @empty {
        <p class="col-span-full text-sm text-slate-500">
          {{ list.loaded() ? 'No encontramos equipos con esos filtros.' : 'Cargando…' }}
        </p>
      }
    </div>

    @if (list.pages() > 1) {
      <nav class="mt-4 flex items-center justify-between text-xs" aria-label="Paginación">
        <button
          type="button"
          class="btn-secondary"
          [disabled]="list.page() === 0"
          (click)="go(list.page() - 1)"
        >
          Anterior
        </button>
        <span>Página {{ list.page() + 1 }} de {{ list.pages() }}</span>
        <button
          type="button"
          class="btn-secondary"
          [disabled]="list.page() + 1 >= list.pages()"
          (click)="go(list.page() + 1)"
        >
          Siguiente
        </button>
      </nav>
    }
  `,
})
export class CatalogoPage implements OnInit {
  private readonly service = inject(CatalogoService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly fotoUrl = fotoUrl;
  protected readonly q = new FormControl('', { nonNullable: true });
  protected readonly categoria = new FormControl('', { nonNullable: true });
  protected readonly desde = new FormControl('', { nonNullable: true });
  protected readonly hasta = new FormControl('', { nonNullable: true });
  protected readonly soloDisponibles = new FormControl(false, { nonNullable: true });

  protected readonly categorias = signal<Categoria[]>([]);
  protected readonly rangeHint = signal<string | null>(null);
  protected readonly list = pagedList<EquipoCatalogo>({
    pageSize: PAGE_SIZE,
    fetch: (page) => this.service.list(this.filters(page)),
    errorMessage: 'No se pudo cargar el catálogo.',
  });

  ngOnInit(): void {
    this.service.categorias().subscribe((categorias) => this.categorias.set(categorias));
    this.q.valueChanges
      .pipe(debounceTime(300), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.go(0));
    merge(
      this.categoria.valueChanges,
      this.desde.valueChanges,
      this.hasta.valueChanges,
      this.soloDisponibles.valueChanges,
    )
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.go(0));
    this.go(0);
  }

  /** Periodo que el cliente trae en el catálogo, para llevarlo a la ficha del equipo. */
  protected carryOver(): Record<string, string> {
    const params: Record<string, string> = {};
    if (this.desde.value) params['desde'] = this.desde.value;
    if (this.hasta.value) params['hasta'] = this.hasta.value;
    return params;
  }

  protected go(page: number): void {
    const periodo = periodFromInputs(this.desde.value, this.hasta.value);
    // Con el periodo a medias o invertido no se pregunta disponibilidad, pero se avisa por qué.
    const started = this.desde.value || this.hasta.value;
    this.rangeHint.set(
      started && !periodo
        ? 'Elige un inicio y un fin (posterior al inicio) para ver la disponibilidad.'
        : null,
    );
    this.list.go(page);
  }

  private filters(page: number): CatalogoFiltros {
    const periodo = periodFromInputs(this.desde.value, this.hasta.value);
    return {
      q: this.q.value.trim(),
      categoria_id: this.categoria.value,
      ...periodo,
      solo_disponibles: periodo && this.soloDisponibles.value ? true : undefined,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    };
  }
}
