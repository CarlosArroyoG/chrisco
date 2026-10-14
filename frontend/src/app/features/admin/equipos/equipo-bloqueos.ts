import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  inject,
  input,
  OnInit,
  output,
  signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { apiErrorMessage } from '../../../core/api/errors';
import { periodFromInputs } from '../../../core/api/dates';
import { Bloqueo } from '../../../core/api/models';
import { EquiposService } from './equipos.service';

const TIPO_LABEL: Record<Bloqueo['tipo'], string> = {
  solicitud: 'Solicitud (reserva provisional)',
  apartado: 'Apartado (esperando requisitos)',
  renta: 'Renta',
  mantenimiento: 'Mantenimiento',
  manual: 'Bloqueo del personal',
};

/** Bloqueos vigentes y futuros de un equipo; el admin puede programar mantenimiento u otros. */
@Component({
  selector: 'app-equipo-bloqueos',
  imports: [DatePipe, ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card mt-4">
      <h2 class="text-sm font-black">Bloqueos y disponibilidad</h2>
      <p class="text-xs text-slate-500">
        Mientras un equipo tiene un bloqueo, nadie más puede rentarlo en ese periodo.
      </p>

      <ul class="mt-3 divide-y text-sm">
        @for (b of bloqueos(); track b.id) {
          <li class="flex flex-wrap items-center justify-between gap-2 py-2">
            <div>
              <p class="font-semibold">{{ tipoLabel[b.tipo] }}</p>
              <p class="text-xs text-slate-500">
                {{ b.desde | date: 'dd/MM/yyyy HH:mm' }} → {{ b.hasta | date: 'dd/MM/yyyy HH:mm' }}
                @if (b.motivo) {
                  · {{ b.motivo }}
                }
                @if (b.vence_en) {
                  · vence {{ b.vence_en | date: 'HH:mm' }}
                }
                @if (b.creado_por_nombre) {
                  · {{ b.creado_por_nombre }}
                }
              </p>
            </div>
            @if (canEdit() && (b.tipo === 'mantenimiento' || b.tipo === 'manual')) {
              <button type="button" class="link text-xs text-rose-700" (click)="release(b)">
                Liberar
              </button>
            }
          </li>
        } @empty {
          <li class="py-2 text-xs text-slate-500">
            {{ loaded() ? 'Sin bloqueos vigentes ni futuros: el equipo está libre.' : 'Cargando…' }}
          </li>
        }
      </ul>

      @if (error()) {
        <p role="alert" class="alert-error mt-2">{{ error() }}</p>
      }

      @if (canEdit()) {
        <form
          [formGroup]="form"
          (ngSubmit)="create()"
          class="mt-4 space-y-3 border-t pt-4"
          novalidate
        >
          <h3 class="text-xs font-black text-slate-500 uppercase">Programar un bloqueo</h3>
          <div class="grid gap-3 sm:grid-cols-4">
            <div>
              <label for="bl-tipo" class="label">Tipo</label>
              <select id="bl-tipo" formControlName="tipo" class="input">
                <option value="mantenimiento">Mantenimiento</option>
                <option value="manual">Otra razón</option>
              </select>
            </div>
            <div>
              <label for="bl-desde" class="label">Desde</label>
              <input id="bl-desde" type="datetime-local" formControlName="desde" class="input" />
            </div>
            <div>
              <label for="bl-hasta" class="label">Hasta</label>
              <input id="bl-hasta" type="datetime-local" formControlName="hasta" class="input" />
            </div>
            <div>
              <label for="bl-motivo" class="label">Motivo</label>
              <input
                id="bl-motivo"
                formControlName="motivo"
                placeholder="Cambio de aceite"
                class="input"
              />
            </div>
          </div>
          <button type="submit" class="btn-primary" [disabled]="form.invalid || busy()">
            {{ busy() ? 'Guardando…' : 'Bloquear equipo' }}
          </button>
        </form>
      }
    </section>
  `,
})
export class EquipoBloqueos implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly service = inject(EquiposService);

  readonly equipoId = input.required<string>();
  readonly canEdit = input.required<boolean>();
  /** Se emite al crear o liberar un bloqueo: cambia la situación actual del equipo. */
  readonly changed = output<void>();

  protected readonly tipoLabel = TIPO_LABEL;
  protected readonly bloqueos = signal<Bloqueo[]>([]);
  protected readonly loaded = signal(false);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = this.fb.group({
    tipo: ['mantenimiento' as 'mantenimiento' | 'manual'],
    desde: ['', Validators.required],
    hasta: ['', Validators.required],
    motivo: ['', [Validators.required, Validators.minLength(3)]],
  });

  ngOnInit(): void {
    this.load();
  }

  protected create(): void {
    const { tipo, desde, hasta, motivo } = this.form.getRawValue();
    const periodo = periodFromInputs(desde, hasta);
    if (!periodo) {
      this.error.set('Elige un inicio y un fin, y que el fin sea posterior al inicio.');
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    this.service
      .createBloqueo(this.equipoId(), { tipo, motivo: motivo.trim(), ...periodo })
      .subscribe({
        next: () => {
          this.busy.set(false);
          this.form.reset({ tipo: 'mantenimiento', desde: '', hasta: '', motivo: '' });
          this.load();
          this.changed.emit();
        },
        error: (err: unknown) => {
          this.busy.set(false);
          this.error.set(apiErrorMessage(err, 'No se pudo crear el bloqueo.'));
        },
      });
  }

  protected release(bloqueo: Bloqueo): void {
    this.error.set(null);
    this.service.releaseBloqueo(bloqueo.id).subscribe({
      next: () => {
        this.load();
        this.changed.emit();
      },
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'No se pudo liberar el bloqueo.')),
    });
  }

  private load(): void {
    this.service.bloqueos(this.equipoId()).subscribe({
      next: (bloqueos) => {
        this.bloqueos.set(bloqueos);
        this.loaded.set(true);
      },
      error: (err: unknown) => {
        this.loaded.set(true);
        this.error.set(apiErrorMessage(err, 'No se pudieron cargar los bloqueos.'));
      },
    });
  }
}
