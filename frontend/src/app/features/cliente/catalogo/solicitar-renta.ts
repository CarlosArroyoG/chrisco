import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, input, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { periodFromInputs, toLocalInput } from '../../../core/api/dates';
import { apiErrorMessage } from '../../../core/api/errors';
import {
  EquipoCatalogo,
  OperadorModo,
  Requisito,
  SolicitudCreada,
  SolicitudIn,
  SolicitudPreview,
  Transporte,
} from '../../../core/api/models';
import { RentasService } from '../../../core/rentas/rentas.service';
import { Countdown } from '../../../shared/countdown/countdown';

const SECTIONS: { tipo: Requisito['tipo']; titulo: string }[] = [
  { tipo: 'documento', titulo: 'Documentos que necesitamos' },
  { tipo: 'condicion', titulo: 'Condiciones' },
  { tipo: 'cargo', titulo: 'Cargos previstos (se cotizan aparte)' },
];

/** Pedir un equipo: se capturan los datos, se revisan sus requisitos y se reserva por 20 minutos. */
@Component({
  selector: 'app-solicitar-renta',
  imports: [DatePipe, ReactiveFormsModule, RouterLink, Countdown],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card mt-4" aria-labelledby="solicitar-titulo">
      <h2 id="solicitar-titulo" class="text-sm font-black">Solicitar este equipo</h2>

      @switch (step()) {
        @case ('form') {
          <form [formGroup]="form" (ngSubmit)="review()" class="mt-3 space-y-3" novalidate>
            <div class="grid gap-3 sm:grid-cols-2">
              <div>
                <label for="sol-desde" class="label">Lo necesito desde *</label>
                <input id="sol-desde" type="datetime-local" formControlName="desde" class="input" />
              </div>
              <div>
                <label for="sol-hasta" class="label">Hasta *</label>
                <input id="sol-hasta" type="datetime-local" formControlName="hasta" class="input" />
              </div>
            </div>
            <div>
              <label for="sol-destino" class="label">Lugar donde se usará *</label>
              <input
                id="sol-destino"
                formControlName="destino"
                placeholder="Autopista Morelia - Guadalajara, km 45"
                class="input"
              />
            </div>

            <fieldset>
              <legend class="label">¿Quién opera el equipo?</legend>
              <label class="flex items-center gap-2 py-1 text-sm">
                <input type="radio" formControlName="operador_modo" value="chrisco" />
                Operador de CHRISCO
              </label>
              <label class="flex items-center gap-2 py-1 text-sm">
                <input type="radio" formControlName="operador_modo" value="cliente" />
                Mi empresa pone su propio operador
              </label>
            </fieldset>

            <fieldset>
              <legend class="label">¿Cómo llega el equipo?</legend>
              <label class="flex items-center gap-2 py-1 text-sm">
                <input type="radio" formControlName="transporte" value="entrega" />
                Que lo entregue CHRISCO en mi obra
              </label>
              <label class="flex items-center gap-2 py-1 text-sm">
                <input type="radio" formControlName="transporte" value="recoge" />
                Lo recojo en el patio ({{ equipo().patio }})
              </label>
            </fieldset>

            <div>
              <label for="sol-notas" class="label">Notas para ventas (opcional)</label>
              <textarea id="sol-notas" formControlName="notas" rows="2" class="input"></textarea>
            </div>

            @if (error()) {
              <p role="alert" class="alert-error">{{ error() }}</p>
            }
            <button type="submit" class="btn-primary" [disabled]="busy()">
              {{ busy() ? 'Revisando…' : 'Revisar solicitud' }}
            </button>
          </form>
        }

        @case ('review') {
          @if (preview(); as p) {
            <dl class="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
              <dt class="text-slate-500">Periodo</dt>
              <dd class="font-semibold">
                {{ payload.desde | date: 'dd/MM/yyyy HH:mm' }} →
                {{ payload.hasta | date: 'dd/MM/yyyy HH:mm' }}
              </dd>
              <dt class="text-slate-500">Lugar</dt>
              <dd class="font-semibold">{{ payload.destino }}</dd>
            </dl>

            @if (p.disponible) {
              <p role="status" class="alert-ok mt-3">
                Está libre en esas fechas. Al confirmar, lo reservamos 20 minutos mientras ventas te
                cotiza.
              </p>
            } @else {
              <p role="alert" class="alert-error mt-3">
                Ese equipo ya no está libre en esas fechas. Cambia el periodo para intentar de
                nuevo.
              </p>
            }

            @for (section of sections; track section.tipo) {
              @if (itemsOf(p.requisitos, section.tipo).length) {
                <h3 class="mt-4 text-xs font-black text-slate-500 uppercase">
                  {{ section.titulo }}
                </h3>
                <ul class="mt-1 space-y-2 text-sm">
                  @for (r of itemsOf(p.requisitos, section.tipo); track r.codigo) {
                    <li>
                      <p class="font-semibold">{{ r.titulo }}</p>
                      <p class="text-xs text-slate-500">{{ r.detalle }}</p>
                    </li>
                  }
                </ul>
              }
            }

            @if (error()) {
              <p role="alert" class="alert-error mt-3">{{ error() }}</p>
            }
            <div class="mt-4 flex flex-wrap gap-2">
              <button type="button" class="btn-secondary" (click)="step.set('form')">
                Cambiar datos
              </button>
              <button
                type="button"
                class="btn-primary"
                [disabled]="!p.disponible || busy()"
                (click)="confirm()"
              >
                {{ busy() ? 'Reservando…' : 'Confirmar y reservar' }}
              </button>
            </div>
          }
        }

        @case ('done') {
          @if (creada(); as c) {
            <div class="mt-3 space-y-3">
              <p role="status" class="alert-ok">
                Solicitud <b>{{ c.folio }}</b> enviada. Reservamos el equipo; avísale a ventas por
                WhatsApp para que te cotice.
              </p>
              @if (c.vence_en) {
                <p class="text-sm">
                  @if (!expired()) {
                    Reservado por
                    <app-countdown [until]="c.vence_en" (expired)="expired.set(true)" /> más.
                  } @else {
                    <span class="font-semibold text-rose-700">
                      La reserva venció. Si ventas aún no te cotiza, vuelve a solicitar el equipo.
                    </span>
                  }
                </p>
              }
              <label for="sol-mensaje" class="label">Mensaje para ventas</label>
              <textarea id="sol-mensaje" readonly rows="9" class="input font-mono text-xs">{{
                c.whatsapp.mensaje
              }}</textarea>
              <div class="flex flex-wrap gap-2">
                @if (c.whatsapp.url) {
                  <a
                    [href]="c.whatsapp.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="btn-primary"
                  >
                    Enviar por WhatsApp
                  </a>
                }
                <button type="button" class="btn-secondary" (click)="copy(c.whatsapp.mensaje)">
                  {{ copied() ? 'Copiado ✓' : 'Copiar mensaje' }}
                </button>
                <a routerLink="/cliente/rentas" class="btn-secondary">Ver mis rentas</a>
              </div>
              @if (!c.whatsapp.url) {
                <p class="text-xs text-slate-500">
                  El número de WhatsApp de ventas aún no está configurado: copia el mensaje y
                  envíalo tú.
                </p>
              }
            </div>
          }
        }
      }
    </section>
  `,
})
export class SolicitarRenta implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly rentas = inject(RentasService);

  readonly equipo = input.required<EquipoCatalogo>();
  /** Periodo con el que el cliente venía filtrando el catálogo (hora local de un datetime-local). */
  readonly desdeInicial = input('');
  readonly hastaInicial = input('');

  protected readonly sections = SECTIONS;
  protected readonly step = signal<'form' | 'review' | 'done'>('form');
  protected readonly preview = signal<SolicitudPreview | null>(null);
  protected readonly creada = signal<SolicitudCreada | null>(null);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly expired = signal(false);
  protected readonly copied = signal(false);
  protected payload!: SolicitudIn;

  protected readonly form = this.fb.group({
    desde: ['', Validators.required],
    hasta: ['', Validators.required],
    destino: ['', [Validators.required, Validators.minLength(5)]],
    operador_modo: ['chrisco' as OperadorModo],
    transporte: ['entrega' as Transporte],
    notas: [''],
  });

  ngOnInit(): void {
    // Sin fechas previas se sugiere mañana de 8:00 a 18:00; el cliente lo ajusta.
    const manana = new Date();
    manana.setDate(manana.getDate() + 1);
    const inicio = new Date(manana.setHours(8, 0, 0, 0));
    const fin = new Date(manana.setHours(18, 0, 0, 0));
    this.form.patchValue({
      desde: this.desdeInicial() || toLocalInput(inicio),
      hasta: this.hastaInicial() || toLocalInput(fin),
    });
  }

  protected itemsOf(items: Requisito[], tipo: Requisito['tipo']): Requisito[] {
    return items.filter((r) => r.tipo === tipo);
  }

  protected review(): void {
    const { desde, hasta, destino, operador_modo, transporte, notas } = this.form.getRawValue();
    const periodo = periodFromInputs(desde, hasta);
    if (!periodo || this.form.controls.destino.invalid) {
      this.error.set('Indica el periodo (el fin después del inicio) y el lugar donde se usará.');
      return;
    }
    this.payload = {
      equipo_id: this.equipo().id,
      ...periodo,
      destino: destino.trim(),
      operador_modo,
      transporte,
      notas: notas.trim() || null,
    };
    this.busy.set(true);
    this.error.set(null);
    this.rentas.preview(this.payload).subscribe({
      next: (preview) => {
        this.busy.set(false);
        this.preview.set(preview);
        this.step.set('review');
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err, 'No se pudo revisar la solicitud.'));
      },
    });
  }

  protected confirm(): void {
    this.busy.set(true);
    this.error.set(null);
    this.rentas.create(this.payload).subscribe({
      next: (creada) => {
        this.busy.set(false);
        this.creada.set(creada);
        this.step.set('done');
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err, 'No se pudo reservar el equipo.'));
      },
    });
  }

  protected copy(message: string): void {
    void navigator.clipboard
      .writeText(message)
      .then(() => this.copied.set(true))
      .catch(() => this.error.set('No se pudo copiar: selecciona el texto y cópialo a mano.'));
  }
}
