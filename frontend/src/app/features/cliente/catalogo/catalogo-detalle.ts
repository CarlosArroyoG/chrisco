import { CurrencyPipe, DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  OnInit,
  signal,
} from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../../core/api/errors';
import { EquipoCatalogo, Ocupacion } from '../../../core/api/models';
import { CatalogoService, fotoUrl } from '../../../core/catalogo/catalogo.service';
import { ETAPAS, TONO_CLASES } from '../../../core/rentas/etapas';
import { Carousel } from '../../../shared/carousel/carousel';
import { Icon } from '../../../shared/icon/icon';
import { RentaPasos } from '../../../shared/renta-pasos/renta-pasos';
import { SolicitarRenta } from './solicitar-renta';

const SITUACION: Record<string, { label: string; classes: string }> = {
  libre: { label: 'Disponible hoy', classes: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  rentado: { label: 'Rentado ahora', classes: 'bg-sky-50 text-sky-700 ring-sky-200' },
  bloqueado: { label: 'No disponible hoy', classes: 'bg-amber-50 text-amber-700 ring-amber-200' },
};

/** Ficha de un equipo del catálogo: galería, descripción, especificaciones, tarifas y el paso a seguir. */
@Component({
  selector: 'app-catalogo-detalle',
  imports: [CurrencyPipe, DatePipe, RouterLink, SolicitarRenta, Carousel, Icon, RentaPasos],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a routerLink="/cliente/catalogo" class="link text-sm">← Volver al catálogo</a>
    @if (error()) {
      <p role="alert" class="alert-error mt-3">{{ error() }}</p>
    }
    @if (equipo(); as e) {
      <div class="mt-4 grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <section aria-label="Fotos del equipo">
          <app-carousel
            [images]="fotos()"
            [label]="e.nombre"
            aspect="aspect-[4/3]"
            [(index)]="selected"
          />
          @if (fotos().length > 1) {
            <div class="mt-3 flex gap-2 overflow-x-auto pb-1">
              @for (foto of e.fotos; track foto.id; let i = $index) {
                <button
                  type="button"
                  (click)="selected.set(i)"
                  [attr.aria-label]="'Ver foto ' + (i + 1)"
                  class="shrink-0 overflow-hidden rounded-xl border-2 transition"
                  [class]="
                    i === selected()
                      ? 'border-chrisco-orange shadow-md'
                      : 'border-transparent opacity-70 hover:opacity-100'
                  "
                >
                  <img [src]="fotoUrl(foto.id, 'thumb')" alt="" class="h-16 w-24 object-cover" />
                </button>
              }
            </div>
          }
        </section>

        <aside class="space-y-4 self-start lg:sticky lg:top-24">
          <div class="card space-y-4">
            <div>
              <p class="eyebrow">{{ e.categoria_nombre }}</p>
              <h1 class="mt-1 text-3xl font-extrabold tracking-tight text-slate-900">
                {{ e.nombre }}
              </h1>
              <p class="mt-1 text-sm text-slate-500">
                {{ e.marca }} {{ e.modelo }}
                @if (e.anio) {
                  · {{ e.anio }}
                }
                · {{ e.patio }}
              </p>
            </div>

            <div class="flex flex-wrap gap-2">
              <span
                class="rounded-full px-3 py-1 text-xs font-bold ring-1 ring-inset"
                [class]="situacion().classes"
                >{{ situacion().label }}</span
              >
              @if (e.requiere_lowboy) {
                <span
                  class="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700"
                  >Se transporta en lowboy</span
                >
              }
              @if (e.requiere_operador_certificado) {
                <span
                  class="rounded-full bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700"
                  >Requiere operador certificado</span
                >
              }
            </div>

            <div class="from-chrisco-dark rounded-2xl bg-linear-to-br to-[#2b3a42] p-5 text-white">
              <div class="flex flex-wrap items-end gap-x-6 gap-y-2">
                @if (e.tarifa_hora) {
                  <p>
                    <span class="text-3xl font-extrabold">{{
                      e.tarifa_hora | currency: 'MXN' : 'symbol-narrow' : '1.0-2'
                    }}</span>
                    <span class="text-sm text-slate-300"> por hora</span>
                  </p>
                }
                @if (e.tarifa_dia) {
                  <p>
                    <span class="text-xl font-bold">{{
                      e.tarifa_dia | currency: 'MXN' : 'symbol-narrow' : '1.0-2'
                    }}</span>
                    <span class="text-sm text-slate-300"> por día</span>
                  </p>
                }
              </div>
              <p class="mt-2 text-xs text-slate-400">
                Más IVA. El flete y otros cargos se cotizan aparte.
              </p>
            </div>

            @if (e.mi_renta; as r) {
              <div class="rounded-2xl p-4 ring-1 ring-inset" [class]="tono(r.estado)">
                <p class="text-sm font-bold">{{ etapa(r.estado).etiqueta }} · {{ r.folio }}</p>
                <p class="mt-0.5 text-xs opacity-80">{{ etapa(r.estado).pista }}</p>
                <div class="mt-3"><app-renta-pasos [estado]="r.estado" /></div>
              </div>
              <a [routerLink]="['/cliente/rentas', r.id]" class="btn-primary w-full">
                {{ etapa(r.estado).accion }} <app-icon name="flecha" class="size-4" />
              </a>
              <button type="button" class="btn-secondary w-full" (click)="irASolicitar()">
                Pedir este equipo para otras fechas
              </button>
            } @else {
              <button
                type="button"
                class="btn-primary w-full py-3 text-base"
                (click)="irASolicitar()"
              >
                Reservar este equipo <app-icon name="flecha" class="size-4" />
              </button>
              <p class="text-center text-xs text-slate-500">
                Se aparta 20 minutos mientras ventas te cotiza.
              </p>
            }
          </div>
        </aside>
      </div>

      @if (e.descripcion || e.specs.length) {
        <section class="card mt-6">
          @if (e.descripcion) {
            <h2 class="text-lg font-bold text-slate-900">Acerca de este equipo</h2>
            <p class="mt-2 leading-relaxed whitespace-pre-line text-slate-600">
              {{ e.descripcion }}
            </p>
          }
          @if (e.specs.length) {
            <h2 class="text-lg font-bold text-slate-900" [class.mt-6]="e.descripcion">
              Especificaciones
            </h2>
            <dl class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              @for (s of e.specs; track s.label) {
                <div class="rounded-xl bg-slate-50 px-4 py-3">
                  <dt class="text-xs text-slate-500">{{ s.label }}</dt>
                  <dd class="font-semibold text-slate-900">
                    {{ s.value }}{{ s.unit ? ' ' + s.unit : '' }}
                  </dd>
                </div>
              }
            </dl>
          }
        </section>
      }

      <section class="card mt-6">
        <h2 class="text-lg font-bold text-slate-900">Disponibilidad en los próximos 90 días</h2>
        @if (ocupado().length) {
          <ul class="mt-3 space-y-2 text-sm">
            @for (o of ocupado(); track o.desde) {
              <li class="flex items-center gap-2 rounded-xl bg-rose-50 px-3 py-2 text-rose-700">
                <app-icon name="reloj" class="size-4" />
                Ocupado del {{ o.desde | date: 'dd/MM/yyyy HH:mm' }} al
                {{ o.hasta | date: 'dd/MM/yyyy HH:mm' }}
              </li>
            }
          </ul>
        } @else {
          <p
            class="mt-3 flex items-center gap-2 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700"
          >
            <app-icon name="check" class="size-4" />
            Sin reservas: disponible en cualquier fecha.
          </p>
        }
        <p class="mt-3 text-xs text-slate-500">
          Fuera de esos horarios el equipo está libre. Las reservas provisionales pueden liberarse
          sin aviso.
        </p>
      </section>

      <div id="solicitar" class="scroll-mt-24">
        <app-solicitar-renta [equipo]="e" [desdeInicial]="desde()" [hastaInicial]="hasta()" />
      </div>
    }
  `,
})
export class CatalogoDetalle implements OnInit {
  private readonly service = inject(CatalogoService);
  private readonly route = inject(ActivatedRoute);

  /** Id de la ruta `/cliente/catalogo/:id`. */
  readonly id = input.required<string>();
  /** Periodo con el que se venía filtrando el catálogo (query params `desde` y `hasta`). */
  readonly desde = input('');
  readonly hasta = input('');

  protected readonly fotoUrl = fotoUrl;
  protected readonly equipo = signal<EquipoCatalogo | null>(null);
  protected readonly selected = signal(0);
  protected readonly ocupado = signal<Ocupacion[]>([]);
  protected readonly error = signal<string | null>(null);

  protected readonly fotos = computed(() =>
    (this.equipo()?.fotos ?? []).map((f) => fotoUrl(f.id, 'full')),
  );
  protected readonly situacion = computed(
    () => SITUACION[this.equipo()?.situacion ?? 'libre'] ?? SITUACION['libre'],
  );

  protected etapa = (estado: keyof typeof ETAPAS) => ETAPAS[estado];
  protected tono = (estado: keyof typeof ETAPAS) => TONO_CLASES[ETAPAS[estado].tono];

  ngOnInit(): void {
    this.service.get(this.id()).subscribe({
      next: (equipo) => {
        this.equipo.set(equipo);
        // `#solicitar` desde el catálogo: baja directo al formulario.
        if (this.route.snapshot.fragment === 'solicitar')
          setTimeout(() => this.irASolicitar(), 150);
      },
      error: (err: unknown) => this.error.set(apiErrorMessage(err, 'No se pudo cargar el equipo.')),
    });
    const hoy = new Date();
    const en90dias = new Date(hoy.getTime() + 90 * 24 * 3600_000);
    this.service.disponibilidad(this.id(), hoy.toISOString(), en90dias.toISOString()).subscribe({
      next: (disponibilidad) => this.ocupado.set(disponibilidad.ocupado),
    });
  }

  protected irASolicitar(): void {
    document.getElementById('solicitar')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}
