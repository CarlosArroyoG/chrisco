import { CurrencyPipe, DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../../core/api/errors';
import { Renta } from '../../../core/api/models';
import { fotoUrl } from '../../../core/catalogo/catalogo.service';
import { ESTADOS_ABIERTOS, ETAPAS, TONO_CLASES } from '../../../core/rentas/etapas';
import { RentasService } from '../../../core/rentas/rentas.service';
import { Countdown } from '../../../shared/countdown/countdown';
import { Icon } from '../../../shared/icon/icon';
import { RentaPasos } from '../../../shared/renta-pasos/renta-pasos';

type Pestana = 'activas' | 'cerradas' | 'otras';

const PESTANAS: { value: Pestana; label: string; texto: string }[] = [
  { value: 'activas', label: 'Activas', texto: 'No tienes rentas en curso.' },
  { value: 'cerradas', label: 'Terminadas', texto: 'Aún no tienes rentas terminadas.' },
  { value: 'otras', label: 'Canceladas y vencidas', texto: 'Nada por aquí.' },
];

/** «Mis rentas» del cliente: una tarjeta por renta, con su foto, su etapa y qué hacer ahora. */
@Component({
  selector: 'app-mis-rentas',
  imports: [CurrencyPipe, DatePipe, RouterLink, Countdown, Icon, RentaPasos],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p class="eyebrow">Seguimiento</p>
        <h1 class="page-title">Mis rentas ({{ rentas().length }})</h1>
      </div>
      <a routerLink="/cliente/catalogo" class="btn-primary">
        Ver catálogo <app-icon name="flecha" class="size-4" />
      </a>
    </div>

    @if (error()) {
      <p role="alert" class="alert-error mt-4">{{ error() }}</p>
    }

    @if (porAtender().length) {
      <section
        class="mt-6 rounded-2xl bg-linear-to-r from-orange-50 to-amber-50 p-4 ring-1 ring-orange-200"
        aria-label="Requieren tu atención"
      >
        <p class="text-sm font-bold text-orange-800">
          {{
            porAtender().length === 1
              ? 'Una renta necesita'
              : porAtender().length + ' rentas necesitan'
          }}
          tu atención
        </p>
        <p class="text-xs text-orange-700">
          Responde la cotización o completa los requisitos para no perder el apartado.
        </p>
      </section>
    }

    <div class="mt-6 flex flex-wrap gap-2" role="tablist" aria-label="Estado de las rentas">
      @for (p of pestanas; track p.value) {
        <button
          type="button"
          role="tab"
          [attr.aria-selected]="pestana() === p.value"
          (click)="pestana.set(p.value)"
          class="rounded-full px-4 py-2 text-sm font-semibold transition"
          [class]="
            pestana() === p.value
              ? 'bg-chrisco-dark text-white shadow-md'
              : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
          "
        >
          {{ p.label }}
          <span class="ml-1 opacity-70">{{ conteo()[p.value] }}</span>
        </button>
      }
    </div>

    <div class="mt-5 grid gap-5 lg:grid-cols-2">
      @for (r of visibles(); track r.id) {
        <article
          class="card shadow-card hover:shadow-lift flex flex-col gap-4 overflow-hidden !p-0 transition duration-200 hover:-translate-y-0.5 sm:flex-row"
          [attr.data-folio]="r.folio"
        >
          <div class="relative sm:w-40 sm:shrink-0">
            @if (r.equipo_foto_id) {
              <img
                [src]="foto(r.equipo_foto_id)"
                [alt]="r.equipo_nombre"
                class="h-44 w-full object-cover sm:h-full"
                loading="lazy"
              />
            } @else {
              <div
                class="flex h-44 w-full items-center justify-center bg-slate-100 text-xs text-slate-400 sm:h-full"
              >
                Sin foto
              </div>
            }
          </div>

          <div class="flex min-w-0 flex-1 flex-col p-5 sm:pl-1">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <span class="font-mono text-xs font-bold text-slate-500">{{ r.folio }}</span>
              <span
                class="rounded-full px-2.5 py-1 text-[11px] font-bold whitespace-nowrap ring-1 ring-inset"
                [class]="tono(r.estado)"
                >{{ etapa(r.estado).etiqueta }}</span
              >
            </div>
            <h2 class="mt-1 text-lg font-bold tracking-tight text-slate-900">
              {{ r.equipo_nombre }}
            </h2>
            <p class="text-xs text-slate-500">{{ r.equipo_codigo }}</p>

            <p class="mt-3 text-sm text-slate-600">
              {{ r.desde | date: 'dd MMM, HH:mm' }} → {{ r.hasta | date: 'dd MMM, HH:mm' }}
            </p>
            <p class="truncate text-xs text-slate-500">{{ r.destino }}</p>

            @if (r.total !== null) {
              <p class="mt-2 text-base font-extrabold text-slate-900">
                {{ r.total | currency: 'MXN' : 'symbol-narrow' : '1.0-0' }}
                <span class="text-xs font-medium text-slate-400"
                  >+ IVA incluido en la cotización</span
                >
              </p>
            }

            @if (r.vence_en) {
              <p class="mt-2 flex items-center gap-1.5 text-xs font-semibold text-amber-700">
                <app-icon name="reloj" class="size-4" />
                {{ r.estado === 'apartada' ? 'Apartado por' : 'Reservado por' }}
                <app-countdown [until]="r.vence_en" />
              </p>
            }

            <div class="mt-4"><app-renta-pasos [estado]="r.estado" /></div>

            <div class="mt-auto flex flex-col gap-3 pt-4">
              <p class="text-xs text-slate-500">{{ etapa(r.estado).pista }}</p>
              <a
                [routerLink]="['/cliente/rentas', r.id]"
                [class]="urgente(r) ? 'btn-primary' : 'btn-secondary'"
              >
                {{ etapa(r.estado).accion }}
                <app-icon name="flecha" class="size-4" />
              </a>
            </div>
          </div>
        </article>
      } @empty {
        <div class="card col-span-full py-12 text-center">
          <span
            class="mx-auto grid size-14 place-items-center rounded-2xl bg-slate-100 text-slate-400"
          >
            <app-icon name="rentas" class="size-7" />
          </span>
          <p class="mt-3 font-semibold text-slate-700">
            {{ loaded() ? textoVacio() : 'Cargando…' }}
          </p>
          @if (loaded() && pestana() === 'activas') {
            <a routerLink="/cliente/catalogo" class="btn-primary mt-4">Explorar el catálogo</a>
          }
        </div>
      }
    </div>
  `,
})
export class MisRentas implements OnInit {
  private readonly service = inject(RentasService);

  protected readonly pestanas = PESTANAS;
  protected readonly rentas = signal<Renta[]>([]);
  protected readonly loaded = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly pestana = signal<Pestana>('activas');

  private readonly grupo = (r: Renta): Pestana => {
    if (ESTADOS_ABIERTOS.includes(r.estado)) return 'activas';
    return r.estado === 'devuelta' || r.estado === 'cerrada' ? 'cerradas' : 'otras';
  };

  protected readonly conteo = computed(() => {
    const total: Record<Pestana, number> = { activas: 0, cerradas: 0, otras: 0 };
    for (const r of this.rentas()) total[this.grupo(r)]++;
    return total;
  });
  protected readonly visibles = computed(() =>
    this.rentas().filter((r) => this.grupo(r) === this.pestana()),
  );
  /** Las que esperan algo del cliente: responder la cotización o cumplir los requisitos. */
  protected readonly porAtender = computed(() =>
    this.rentas().filter((r) => r.estado === 'cotizada' || r.estado === 'apartada'),
  );
  protected readonly textoVacio = computed(
    () => PESTANAS.find((p) => p.value === this.pestana())?.texto ?? '',
  );

  protected etapa = (estado: Renta['estado']) => ETAPAS[estado];
  protected tono = (estado: Renta['estado']) => TONO_CLASES[ETAPAS[estado].tono];
  protected foto = (id: string) => fotoUrl(id, 'thumb');
  protected urgente = (r: Renta) => r.estado === 'cotizada' || r.estado === 'apartada';

  ngOnInit(): void {
    this.service.list({ limit: 100 }).subscribe({
      next: (page) => {
        this.rentas.set(page.items);
        this.loaded.set(true);
      },
      error: (err: unknown) => {
        this.loaded.set(true);
        this.error.set(apiErrorMessage(err, 'No se pudieron cargar tus rentas.'));
      },
    });
  }
}
