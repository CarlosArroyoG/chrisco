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
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { catchError, of } from 'rxjs';
import { apiErrorMessage } from '../../core/api/errors';
import { Cotizacion, Renta, Requisito, Whatsapp } from '../../core/api/models';
import { AuthService } from '../../core/auth/auth.service';
import { RentasService } from '../../core/rentas/rentas.service';
import { Countdown } from '../../shared/countdown/countdown';
import { StatusBadge } from '../../shared/status-badge/status-badge';
import { CotizacionEditor } from './cotizacion-editor';
import { CumplimientoPanel } from './cumplimiento-panel';
import { MovimientosPanel } from './movimientos-panel';
import { RentaPasos } from '../../shared/renta-pasos/renta-pasos';
import { Icon } from '../../shared/icon/icon';
import { fotoUrl } from '../../core/catalogo/catalogo.service';
import { ETAPAS } from '../../core/rentas/etapas';
import { CotizacionView } from './cotizacion-view';

const SECTIONS: { tipo: Requisito['tipo']; titulo: string }[] = [
  { tipo: 'documento', titulo: 'Documentos' },
  { tipo: 'condicion', titulo: 'Condiciones' },
  { tipo: 'cargo', titulo: 'Cargos previstos' },
];

const OPERADOR = { chrisco: 'Operador de CHRISCO', cliente: 'Operador de la empresa cliente' };
const TRANSPORTE = { entrega: 'Entrega CHRISCO en la obra', recoge: 'Lo recoge el cliente' };

/** Detalle de una renta, para el cliente (su empresa) y para el personal. */
@Component({
  selector: 'app-renta-detalle',
  imports: [
    CurrencyPipe,
    DatePipe,
    ReactiveFormsModule,
    RouterLink,
    StatusBadge,
    Countdown,
    CotizacionView,
    CotizacionEditor,
    CumplimientoPanel,
    MovimientosPanel,
    RentaPasos,
    Icon,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a [routerLink]="basePath()" class="link text-xs">← Volver a rentas</a>
    @if (error()) {
      <p role="alert" class="alert-error mt-3">{{ error() }}</p>
    }
    @if (renta(); as r) {
      <section class="card mt-3 overflow-hidden !p-0">
        <div class="grid md:grid-cols-[17rem_1fr]">
          <div class="relative min-h-44 bg-slate-100">
            @if (r.equipo_foto_id) {
              <img
                [src]="foto(r.equipo_foto_id)"
                [alt]="r.equipo_nombre"
                class="absolute inset-0 size-full object-cover"
              />
            } @else {
              <div class="absolute inset-0 grid place-items-center text-slate-300">
                <app-icon name="equipos" class="size-14" />
              </div>
            }
          </div>
          <div class="p-6">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <h1 class="font-mono text-2xl font-black tracking-tight">{{ r.folio }}</h1>
              <app-status-badge [status]="r.estado" />
            </div>
            <p class="mt-1 text-lg font-semibold text-slate-800">
              {{ r.equipo_nombre }}
              <span class="text-sm font-medium text-slate-400">({{ r.equipo_codigo }})</span>
            </p>
            <p class="text-sm text-slate-500">{{ r.empresa_razon_social }}</p>
            <div class="mt-5"><app-renta-pasos [estado]="r.estado" [etiquetas]="false" /></div>
            @if (isClient() && r.estado !== 'solicitada' && etapa(r.estado); as e) {
              <p class="mt-3 text-sm font-medium text-slate-600">{{ e.pista }}</p>
            }

            @if (r.estado === 'solicitada' && r.vence_en && !expired()) {
              <p class="mt-3 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
                Equipo reservado
                <app-countdown [until]="r.vence_en" (expired)="expired.set(true)" /> más mientras
                ventas cotiza.
              </p>
            }
            @if (r.estado === 'apartada' && r.vence_en) {
              <p role="status" class="alert-ok mt-2">
                Equipo apartado.
                @if (isClient()) {
                  Tienes
                  <app-countdown [until]="r.vence_en" (expired)="expired.set(true)" /> para cumplir
                  los requisitos y depositar el anticipo.
                } @else {
                  Faltan <app-countdown [until]="r.vence_en" (expired)="expired.set(true)" /> para
                  que venza el apartado si el cliente no cumple.
                }
              </p>
            }
            @if (r.estado === 'vencida') {
              <p class="alert-error mt-2">
                La reserva venció y el equipo volvió a estar disponible. Puedes volver a
                solicitarlo.
              </p>
            }
            @if (r.motivo_cierre && (r.estado === 'rechazada' || r.estado === 'cancelada')) {
              <p class="alert-error mt-2">{{ r.motivo_cierre }}</p>
            }
          </div>
        </div>

        <div class="border-t border-slate-100 p-6">
          <dl class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div class="rounded-xl bg-slate-50 px-4 py-3">
              <dt class="label !mb-0.5">Periodo</dt>
              <dd class="text-sm font-semibold text-slate-800">
                {{ r.desde | date: 'dd/MM/yyyy HH:mm' }} → {{ r.hasta | date: 'dd/MM/yyyy HH:mm' }}
              </dd>
            </div>
            <div class="rounded-xl bg-slate-50 px-4 py-3">
              <dt class="label !mb-0.5">Lugar</dt>
              <dd class="text-sm font-semibold text-slate-800">{{ r.destino }}</dd>
            </div>
            <div class="rounded-xl bg-slate-50 px-4 py-3">
              <dt class="label !mb-0.5">Solicitó</dt>
              <dd class="text-sm font-semibold text-slate-800">{{ r.solicitante_nombre }}</dd>
            </div>
            <div class="rounded-xl bg-slate-50 px-4 py-3">
              <dt class="label !mb-0.5">Operador</dt>
              <dd class="text-sm font-semibold text-slate-800">{{ operador[r.operador_modo] }}</dd>
            </div>
            <div class="rounded-xl bg-slate-50 px-4 py-3">
              <dt class="label !mb-0.5">Traslado</dt>
              <dd class="text-sm font-semibold text-slate-800">{{ transporte[r.transporte] }}</dd>
            </div>
            @if (r.total !== null) {
              <div class="rounded-xl bg-orange-50 px-4 py-3">
                <dt class="label !mb-0.5">Total cotizado</dt>
                <dd class="text-sm font-extrabold text-orange-700">
                  {{ r.total | currency: 'MXN' : 'symbol-narrow' : '1.0-2' }}
                </dd>
              </div>
            }
            @if (r.notas) {
              <div class="rounded-xl bg-slate-50 px-4 py-3 sm:col-span-2 lg:col-span-3">
                <dt class="label !mb-0.5">Notas</dt>
                <dd class="text-sm text-slate-800">{{ r.notas }}</dd>
              </div>
            }
          </dl>

          @if (canCancel()) {
            <div class="mt-4 flex items-center gap-3 text-xs">
              @if (confirmCancel()) {
                <span>¿Cancelar esta solicitud?</span>
                <button type="button" class="link text-rose-700" (click)="cancel()">
                  Sí, cancelar
                </button>
                <button type="button" class="link" (click)="confirmCancel.set(false)">No</button>
              } @else {
                <button type="button" class="btn-secondary" (click)="confirmCancel.set(true)">
                  Cancelar solicitud
                </button>
              }
            </div>
          }
        </div>
      </section>

      @if (cotizacion(); as c) {
        <section class="card mt-4">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 class="text-lg font-bold text-slate-900">Cotización</h2>
            @if (c.estado === 'aceptada') {
              <span
                class="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-bold text-emerald-800"
                >Aceptada</span
              >
            }
          </div>
          <div class="mt-3"><app-cotizacion-view [cotizacion]="c" /></div>

          @if (canAnswer()) {
            <div class="mt-4 flex flex-wrap items-center gap-3">
              <button type="button" class="btn-primary" [disabled]="busy()" (click)="accept()">
                Aceptar cotización
              </button>
              @if (confirmDecline()) {
                <span class="text-xs">¿Rechazar la cotización?</span>
                <button type="button" class="link text-xs text-rose-700" (click)="decline()">
                  Sí, rechazar
                </button>
                <button type="button" class="link text-xs" (click)="confirmDecline.set(false)">
                  No
                </button>
              } @else {
                <button type="button" class="btn-secondary" (click)="confirmDecline.set(true)">
                  Rechazar
                </button>
              }
            </div>
            <p class="mt-2 text-[11px] text-slate-500">
              Al aceptar, el equipo queda apartado unas horas para que cumplas los requisitos y
              deposites el anticipo de
              {{ c.anticipo_monto | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}.
            </p>
          }
        </section>
      } @else if (isClientWaiting()) {
        <p class="card mt-4 text-sm text-slate-600">
          Ventas está preparando tu cotización. Te avisaremos por correo cuando esté lista.
        </p>
      }

      @if (conCumplimiento()) {
        <app-cumplimiento-panel [renta]="r" (changed)="reload()" />
      }
      @if (conMovimientos()) {
        <app-movimientos-panel [renta]="r" (changed)="reload()" />
      }

      @if (canQuote()) {
        <section class="card mt-4">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 class="text-lg font-bold text-slate-900">
              {{ cotizacion() ? 'Nueva versión de la cotización' : 'Cotizar' }}
            </h2>
            @if (cotizacion() && !editing()) {
              <button type="button" class="btn-secondary" (click)="editing.set(true)">
                Cambiar la cotización
              </button>
            }
          </div>
          @if (!cotizacion() || editing()) {
            <div class="mt-3">
              <app-cotizacion-editor [renta]="r" (quoted)="onQuoted()" />
            </div>
          }

          <form
            [formGroup]="rejectForm"
            (ngSubmit)="rejectRequest()"
            class="mt-4 space-y-2 border-t pt-4"
            novalidate
          >
            <label for="rej-motivo" class="label"
              >No podemos atender esta solicitud (el motivo le llega al cliente)</label
            >
            <input id="rej-motivo" formControlName="motivo" class="input" />
            <button type="submit" class="btn-danger" [disabled]="rejectForm.invalid || busy()">
              Rechazar solicitud
            </button>
          </form>
        </section>
      }

      <section class="card mt-4">
        <h2 class="text-lg font-bold text-slate-900">Requisitos</h2>
        @for (section of sections; track section.tipo) {
          @if (itemsOf(r.requisitos, section.tipo).length) {
            <h3 class="eyebrow mt-5">{{ section.titulo }}</h3>
            <ul class="mt-2 grid gap-3 text-sm sm:grid-cols-2">
              @for (item of itemsOf(r.requisitos, section.tipo); track item.codigo) {
                <li
                  class="rounded-xl border-l-4 bg-slate-50 px-4 py-3"
                  [class]="acento[section.tipo]"
                >
                  <p class="font-semibold text-slate-900">{{ item.titulo }}</p>
                  <p class="text-xs text-slate-500">{{ item.detalle }}</p>
                </li>
              }
            </ul>
          }
        }
      </section>

      @if (isClient() && r.estado === 'solicitada' && whatsapp(); as w) {
        <section class="card mt-4">
          <h2 class="text-lg font-bold text-slate-900">Mensaje para ventas</h2>
          <textarea
            readonly
            rows="8"
            class="input mt-2 font-mono text-xs"
            aria-label="Mensaje para ventas"
            >{{ w.mensaje }}</textarea>
          @if (w.url) {
            <a
              [href]="w.url"
              target="_blank"
              rel="noopener noreferrer"
              class="btn-primary mt-3 inline-block"
            >
              Enviar por WhatsApp
            </a>
          }
        </section>
      }
    }
  `,
})
export class RentaDetalle implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly service = inject(RentasService);
  private readonly auth = inject(AuthService);

  /** Id de la ruta `.../rentas/:id`. */
  readonly id = input.required<string>();

  protected readonly sections = SECTIONS;
  protected readonly acento: Record<Requisito['tipo'], string> = {
    documento: 'border-sky-400',
    condicion: 'border-amber-400',
    cargo: 'border-slate-300',
  };
  protected readonly foto = (id: string) => fotoUrl(id, 'full');
  protected readonly etapa = (estado: Renta['estado']) => ETAPAS[estado];
  protected readonly operador = OPERADOR;
  protected readonly transporte = TRANSPORTE;
  protected readonly renta = signal<Renta | null>(null);
  protected readonly cotizacion = signal<Cotizacion | null>(null);
  protected readonly whatsapp = signal<Whatsapp | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly expired = signal(false);
  protected readonly busy = signal(false);
  protected readonly editing = signal(false);
  protected readonly confirmCancel = signal(false);
  protected readonly confirmDecline = signal(false);

  protected readonly rejectForm = this.fb.group({
    motivo: ['', [Validators.required, Validators.minLength(5)]],
  });

  protected readonly isClient = computed(() => this.auth.user()?.role === 'cliente');
  /** El operador de CHRISCO solo entrega y recibe equipos: no ve dinero ni cotizaciones. */
  protected readonly isOperador = computed(() => this.auth.user()?.role === 'operador');
  protected readonly isStaff = computed(() => !this.isClient() && !this.isOperador());
  protected readonly basePath = computed(() => {
    if (this.isClient()) return '/cliente/rentas';
    return this.isOperador() ? '/operador' : '/admin/rentas';
  });
  protected readonly canCancel = computed(() => {
    const estado = this.renta()?.estado;
    return estado === 'solicitada' || estado === 'cotizada' || estado === 'apartada';
  });
  /** Ventas puede cotizar mientras la solicitud siga abierta. */
  protected readonly canQuote = computed(() => {
    const estado = this.renta()?.estado;
    return this.isStaff() && (estado === 'solicitada' || estado === 'cotizada');
  });
  /** El cliente responde cuando hay una cotización vigente en una solicitud cotizada. */
  protected readonly canAnswer = computed(
    () =>
      this.isClient() &&
      this.renta()?.estado === 'cotizada' &&
      this.cotizacion()?.estado === 'vigente',
  );
  /** Con cotización aceptada hay requisitos que cumplir y pagos que seguir. */
  protected readonly conCumplimiento = computed(() => {
    const estado = this.renta()?.estado;
    return (
      !this.isOperador() &&
      (estado === 'apartada' ||
        estado === 'confirmada' ||
        estado === 'en_renta' ||
        estado === 'devuelta' ||
        estado === 'cerrada')
    );
  });
  /** Desde que la renta se confirma hay entrega, devolución y cierre que seguir. */
  protected readonly conMovimientos = computed(() => {
    const estado = this.renta()?.estado;
    return (
      estado === 'confirmada' ||
      estado === 'en_renta' ||
      estado === 'devuelta' ||
      estado === 'cerrada'
    );
  });
  protected readonly isClientWaiting = computed(
    () => this.isClient() && this.renta()?.estado === 'solicitada',
  );

  ngOnInit(): void {
    this.reload();
  }

  protected itemsOf(items: Requisito[], tipo: Requisito['tipo']): Requisito[] {
    return items.filter((r) => r.tipo === tipo);
  }

  /** Vuelve a pedir la renta y su cotización (404 = todavía no hay). */
  protected reload(): void {
    this.service.get(this.id()).subscribe({
      next: (renta) => {
        this.renta.set(renta);
        this.expired.set(false);
        if (this.isClient() && renta.estado === 'solicitada') {
          this.service.whatsapp(renta.id).subscribe((w) => this.whatsapp.set(w));
        } else {
          this.whatsapp.set(null);
        }
      },
      error: (err: unknown) => this.error.set(apiErrorMessage(err, 'No se pudo cargar la renta.')),
    });
    if (this.isOperador()) return; // el operador no ve cotizaciones
    this.service
      .cotizacion(this.id())
      .pipe(catchError(() => of(null)))
      .subscribe((cotizacion) => this.cotizacion.set(cotizacion));
  }

  /** Ejecuta una acción sobre la renta y refresca la pantalla; muestra el error si falla. */
  private act(request: ReturnType<RentasService['cancel']>, failure: string): void {
    this.busy.set(true);
    this.error.set(null);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.reload();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err, failure));
        this.reload();
      },
    });
  }

  protected onQuoted(): void {
    this.editing.set(false);
    this.reload();
  }

  protected cancel(): void {
    this.confirmCancel.set(false);
    this.act(this.service.cancel(this.id()), 'No se pudo cancelar la solicitud.');
  }

  protected accept(): void {
    this.act(this.service.aceptar(this.id()), 'No se pudo aceptar la cotización.');
  }

  protected decline(): void {
    this.confirmDecline.set(false);
    this.act(this.service.rechazarCotizacion(this.id()), 'No se pudo rechazar la cotización.');
  }

  protected rejectRequest(): void {
    if (this.rejectForm.invalid) return;
    this.act(
      this.service.rechazarSolicitud(this.id(), this.rejectForm.getRawValue().motivo.trim()),
      'No se pudo rechazar la solicitud.',
    );
  }
}
