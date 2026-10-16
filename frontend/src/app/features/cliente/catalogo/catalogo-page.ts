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
import { ETAPAS, TONO_CLASES } from '../../../core/rentas/etapas';
import { Carousel } from '../../../shared/carousel/carousel';
import { Icon } from '../../../shared/icon/icon';

const PAGE_SIZE = 12;

type Situacion = '' | 'libre' | 'rentado';

const SEGMENTOS: { value: Situacion; label: string }[] = [
  { value: '', label: 'Todos' },
  { value: 'libre', label: 'Disponibles hoy' },
  { value: 'rentado', label: 'Rentados' },
];

const SITUACION: Record<string, { label: string; classes: string }> = {
  libre: { label: 'Disponible hoy', classes: 'bg-emerald-500 text-white' },
  rentado: { label: 'Rentado ahora', classes: 'bg-sky-500 text-white' },
  bloqueado: { label: 'No disponible hoy', classes: 'bg-amber-500 text-white' },
};

/** Catálogo de maquinaria para clientes con empresa aprobada: tarjetas grandes y visuales. */
@Component({
  selector: 'app-catalogo-page',
  imports: [CurrencyPipe, ReactiveFormsModule, RouterLink, Carousel, Icon],
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

    <div class="card relative -mt-6 mx-3 grid gap-3 sm:mx-6 sm:grid-cols-3">
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

    <div
      class="mt-6 flex flex-wrap items-center gap-2"
      role="group"
      aria-label="Situación del equipo"
    >
      @for (s of segmentos; track s.value) {
        <button
          type="button"
          [attr.aria-pressed]="situacion.value === s.value"
          (click)="situacion.setValue(s.value)"
          class="rounded-full px-4 py-2 text-sm font-semibold transition"
          [class]="
            situacion.value === s.value
              ? 'bg-chrisco-dark text-white shadow-md'
              : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
          "
        >
          {{ s.label }}
        </button>
      }
    </div>

    @if (list.error()) {
      <p role="alert" class="alert-error mt-3">{{ list.error() }}</p>
    }

    <div class="mt-6 grid gap-6 lg:grid-cols-2">
      @for (e of list.items(); track e.id) {
        <article
          class="card shadow-card hover:shadow-lift flex flex-col overflow-hidden !p-0 transition duration-200 hover:-translate-y-1"
          [attr.data-equipo]="e.nombre"
        >
          <app-carousel
            [images]="fotos(e)"
            [label]="e.nombre"
            aspect="aspect-[16/10]"
            rounded="rounded-none"
          >
            <span
              class="absolute top-3 left-3 rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-bold text-slate-700 shadow-sm backdrop-blur"
              >{{ e.categoria_nombre }}</span
            >
            <span
              class="absolute top-3 right-3 rounded-full px-2.5 py-1 text-[11px] font-bold shadow-sm"
              [class]="estado(e).classes"
              >{{ estado(e).label }}</span
            >
          </app-carousel>

          <div class="flex flex-1 flex-col p-6">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <h2 class="text-xl font-bold tracking-tight text-slate-900">
                  <a
                    [routerLink]="['/cliente/catalogo', e.id]"
                    [queryParams]="carryOver()"
                    class="hover:text-chrisco-orange-dark transition"
                    >{{ e.nombre }}</a
                  >
                </h2>
                <p class="text-sm text-slate-500">
                  {{ e.marca }} {{ e.modelo }}
                  @if (e.anio) {
                    · {{ e.anio }}
                  }
                  · {{ e.patio }}
                </p>
              </div>
            </div>

            <div class="mt-3 flex flex-wrap gap-2">
              @if (e.requiere_lowboy) {
                <span
                  class="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700"
                  >Se entrega en lowboy</span
                >
              }
              @if (e.requiere_operador_certificado) {
                <span
                  class="rounded-full bg-violet-50 px-2.5 py-1 text-xs font-semibold text-violet-700"
                  >Operador certificado</span
                >
              }
              @if (e.disponible === true) {
                <span
                  class="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700"
                  >Disponible en esas fechas</span
                >
              } @else if (e.disponible === false) {
                <span class="rounded-full bg-rose-50 px-2.5 py-1 text-xs font-bold text-rose-700"
                  >Ocupado en esas fechas</span
                >
              }
            </div>

            @if (e.descripcion) {
              <p class="mt-4 line-clamp-3 text-sm leading-relaxed text-slate-600">
                {{ e.descripcion }}
              </p>
            }

            @if (e.specs.length) {
              <dl class="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
                @for (s of e.specs.slice(0, 6); track s.label) {
                  <div class="rounded-xl bg-slate-50 px-3 py-2">
                    <dt class="truncate text-[11px] text-slate-500">{{ s.label }}</dt>
                    <dd class="truncate text-sm font-semibold text-slate-800">
                      {{ s.value }}{{ s.unit ? ' ' + s.unit : '' }}
                    </dd>
                  </div>
                }
              </dl>
            }

            <div class="mt-auto pt-5">
              @if (e.mi_renta; as r) {
                <div class="rounded-2xl p-4 ring-1 ring-inset" [class]="tono(r.estado)">
                  <p class="text-sm font-bold">{{ etapa(r.estado).etiqueta }} · {{ r.folio }}</p>
                  <p class="text-xs opacity-80">{{ etapa(r.estado).pista }}</p>
                </div>
              }
              <div class="mt-4 flex flex-wrap items-end justify-between gap-3">
                <p class="text-2xl font-extrabold tracking-tight text-slate-900">
                  @if (e.tarifa_hora) {
                    {{ e.tarifa_hora | currency: 'MXN' : 'symbol-narrow' : '1.0-2'
                    }}<span class="text-sm font-semibold text-slate-500">/h</span>
                  }
                  @if (e.tarifa_hora && e.tarifa_dia) {
                    <span class="text-slate-300"> · </span>
                  }
                  @if (e.tarifa_dia) {
                    <span class="text-base font-semibold text-slate-600"
                      >{{ e.tarifa_dia | currency: 'MXN' : 'symbol-narrow' : '1.0-2' }}/día</span
                    >
                  }
                </p>
                @if (e.mi_renta; as r) {
                  <a [routerLink]="['/cliente/rentas', r.id]" class="btn-primary">
                    {{ etapa(r.estado).accion }}
                    <app-icon name="flecha" class="size-4" />
                  </a>
                } @else {
                  <a
                    [routerLink]="['/cliente/catalogo', e.id]"
                    [queryParams]="carryOver()"
                    fragment="solicitar"
                    [class]="e.disponible === false ? 'btn-secondary' : 'btn-primary'"
                  >
                    {{ e.disponible === false ? 'Ver disponibilidad' : 'Reservar este equipo' }}
                    <app-icon name="flecha" class="size-4" />
                  </a>
                }
              </div>
            </div>
          </div>
        </article>
      } @empty {
        <p class="col-span-full py-10 text-center text-sm text-slate-500">
          {{ list.loaded() ? 'No encontramos equipos con esos filtros.' : 'Cargando…' }}
        </p>
      }
    </div>

    @if (list.pages() > 1) {
      <nav class="mt-6 flex items-center justify-between text-sm" aria-label="Paginación">
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

  protected readonly segmentos = SEGMENTOS;
  protected readonly q = new FormControl('', { nonNullable: true });
  protected readonly categoria = new FormControl('', { nonNullable: true });
  protected readonly desde = new FormControl('', { nonNullable: true });
  protected readonly hasta = new FormControl('', { nonNullable: true });
  protected readonly soloDisponibles = new FormControl(false, { nonNullable: true });
  protected readonly situacion = new FormControl<Situacion>('', { nonNullable: true });

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
      this.situacion.valueChanges,
    )
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.go(0));
    this.go(0);
  }

  protected fotos(e: EquipoCatalogo): string[] {
    return e.fotos.map((f) => fotoUrl(f.id, 'full'));
  }

  protected estado(e: EquipoCatalogo): { label: string; classes: string } {
    return SITUACION[e.situacion ?? 'libre'] ?? SITUACION['libre'];
  }

  protected etapa = (estado: keyof typeof ETAPAS) => ETAPAS[estado];
  protected tono = (estado: keyof typeof ETAPAS) => TONO_CLASES[ETAPAS[estado].tono];

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
      situacion: this.situacion.value || undefined,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    };
  }
}
