import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  OnInit,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../core/api/errors';
import { Renta, Requisito, Whatsapp } from '../../core/api/models';
import { AuthService } from '../../core/auth/auth.service';
import { RentasService } from '../../core/rentas/rentas.service';
import { Countdown } from '../../shared/countdown/countdown';
import { StatusBadge } from '../../shared/status-badge/status-badge';

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
  imports: [DatePipe, RouterLink, StatusBadge, Countdown],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a [routerLink]="basePath()" class="link text-xs">← Volver a rentas</a>
    @if (error()) {
      <p role="alert" class="alert-error mt-3">{{ error() }}</p>
    }
    @if (renta(); as r) {
      <section class="card mt-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h1 class="font-mono text-lg font-black">{{ r.folio }}</h1>
          <app-status-badge [status]="r.estado" />
        </div>

        @if (r.estado === 'solicitada' && r.vence_en && !expired()) {
          <p class="mt-2 text-sm">
            Equipo reservado
            <app-countdown [until]="r.vence_en" (expired)="expired.set(true)" /> más mientras ventas
            cotiza.
          </p>
        }
        @if (r.estado === 'vencida') {
          <p class="alert-error mt-2">
            La reserva venció y el equipo volvió a estar disponible. Puedes volver a solicitarlo.
          </p>
        }

        <dl class="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <div>
            <dt class="label">Equipo</dt>
            <dd>{{ r.equipo_nombre }} ({{ r.equipo_codigo }})</dd>
          </div>
          <div>
            <dt class="label">Empresa</dt>
            <dd>{{ r.empresa_razon_social }}</dd>
          </div>
          <div>
            <dt class="label">Periodo</dt>
            <dd>
              {{ r.desde | date: 'dd/MM/yyyy HH:mm' }} → {{ r.hasta | date: 'dd/MM/yyyy HH:mm' }}
            </dd>
          </div>
          <div>
            <dt class="label">Solicitó</dt>
            <dd>{{ r.solicitante_nombre }}</dd>
          </div>
          <div>
            <dt class="label">Lugar</dt>
            <dd>{{ r.destino }}</dd>
          </div>
          <div>
            <dt class="label">Operador</dt>
            <dd>{{ operador[r.operador_modo] }}</dd>
          </div>
          <div>
            <dt class="label">Traslado</dt>
            <dd>{{ transporte[r.transporte] }}</dd>
          </div>
          @if (r.notas) {
            <div>
              <dt class="label">Notas</dt>
              <dd>{{ r.notas }}</dd>
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
      </section>

      <section class="card mt-4">
        <h2 class="text-sm font-black">Requisitos</h2>
        @for (section of sections; track section.tipo) {
          @if (itemsOf(r.requisitos, section.tipo).length) {
            <h3 class="mt-3 text-xs font-black text-slate-500 uppercase">{{ section.titulo }}</h3>
            <ul class="mt-1 space-y-2 text-sm">
              @for (item of itemsOf(r.requisitos, section.tipo); track item.codigo) {
                <li>
                  <p class="font-semibold">{{ item.titulo }}</p>
                  <p class="text-xs text-slate-500">{{ item.detalle }}</p>
                </li>
              }
            </ul>
          }
        }
      </section>

      @if (!isStaff() && r.estado === 'solicitada' && whatsapp(); as w) {
        <section class="card mt-4">
          <h2 class="text-sm font-black">Mensaje para ventas</h2>
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
  private readonly service = inject(RentasService);
  private readonly auth = inject(AuthService);

  /** Id de la ruta `.../rentas/:id`. */
  readonly id = input.required<string>();

  protected readonly sections = SECTIONS;
  protected readonly operador = OPERADOR;
  protected readonly transporte = TRANSPORTE;
  protected readonly renta = signal<Renta | null>(null);
  protected readonly whatsapp = signal<Whatsapp | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly expired = signal(false);
  protected readonly confirmCancel = signal(false);

  protected readonly isStaff = computed(() => this.auth.user()?.role !== 'cliente');
  protected readonly basePath = computed(() =>
    this.isStaff() ? '/admin/rentas' : '/cliente/rentas',
  );
  protected readonly canCancel = computed(() => {
    const estado = this.renta()?.estado;
    return estado === 'solicitada' || estado === 'cotizada' || estado === 'apartada';
  });

  ngOnInit(): void {
    this.service.get(this.id()).subscribe({
      next: (renta) => {
        this.renta.set(renta);
        if (!this.isStaff() && renta.estado === 'solicitada') {
          this.service.whatsapp(renta.id).subscribe((w) => this.whatsapp.set(w));
        }
      },
      error: (err: unknown) => this.error.set(apiErrorMessage(err, 'No se pudo cargar la renta.')),
    });
  }

  protected itemsOf(items: Requisito[], tipo: Requisito['tipo']): Requisito[] {
    return items.filter((r) => r.tipo === tipo);
  }

  protected cancel(): void {
    this.confirmCancel.set(false);
    this.service.cancel(this.id()).subscribe({
      next: (renta) => {
        this.renta.set(renta);
        this.whatsapp.set(null);
      },
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'No se pudo cancelar la solicitud.')),
    });
  }
}
