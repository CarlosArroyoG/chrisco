import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, input, OnInit, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { apiErrorMessage } from '../../../core/api/errors';
import { PlanMantenimiento } from '../../../core/api/models';
import { MantenimientoEstado } from '../../../shared/mantenimiento-estado/mantenimiento-estado';
import { MantenimientoService } from './mantenimiento.service';

/** Planes de mantenimiento de un equipo; el admin los da de alta y registra los servicios hechos. */
@Component({
  selector: 'app-equipo-mantenimiento',
  imports: [DatePipe, DecimalPipe, ReactiveFormsModule, MantenimientoEstado],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card mt-4" aria-labelledby="mant-titulo">
      <h2 id="mant-titulo" class="text-sm font-black">Mantenimiento</h2>
      <p class="text-xs text-slate-500">
        Cada plan avisa por correo a los administradores cuando se acerca y cuando vence, según las
        horas del horómetro y los días transcurridos.
      </p>

      <ul class="mt-3 divide-y text-sm" aria-label="Planes de mantenimiento">
        @for (p of planes(); track p.id) {
          <li class="py-3" [attr.data-plan]="p.nombre">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p class="font-semibold">{{ p.nombre }}</p>
                <p class="text-xs text-slate-500">
                  Cada
                  @if (p.cada_horas !== null) {
                    {{ p.cada_horas | number: '1.0-1' }} h
                  }
                  @if (p.cada_horas !== null && p.cada_dias !== null) {
                    o
                  }
                  @if (p.cada_dias !== null) {
                    {{ p.cada_dias }} días
                  }
                  · último: {{ p.ultima_fecha | date: 'dd/MM/yyyy' }} a las
                  {{ p.ultimo_horometro | number: '1.0-1' }} h
                </p>
              </div>
              <app-mantenimiento-estado [plan]="p" />
            </div>
            @if (canEdit()) {
              <div class="mt-2 flex flex-wrap items-center gap-3 text-xs">
                @if (hecho() === p.id) {
                  <form
                    [formGroup]="hechoForm"
                    (ngSubmit)="registrarHecho(p)"
                    class="flex flex-wrap items-end gap-2"
                  >
                    <div>
                      <label [for]="'hecho-notas-' + p.id" class="label">Notas (opcional)</label>
                      <input
                        [id]="'hecho-notas-' + p.id"
                        formControlName="notas"
                        class="input"
                        maxlength="300"
                      />
                    </div>
                    <button type="submit" class="btn-primary" [disabled]="busy()">
                      Registrar servicio
                    </button>
                    <button type="button" class="link" (click)="hecho.set(null)">Cancelar</button>
                  </form>
                } @else {
                  <button type="button" class="btn-secondary" (click)="hecho.set(p.id)">
                    Servicio realizado
                  </button>
                  <button type="button" class="link text-rose-700" (click)="borrar(p)">
                    Quitar plan
                  </button>
                }
              </div>
            }
          </li>
        } @empty {
          <li class="py-2 text-xs text-slate-500">
            {{ loaded() ? 'Este equipo no tiene planes de mantenimiento.' : 'Cargando…' }}
          </li>
        }
      </ul>

      @if (error()) {
        <p role="alert" class="alert-error mt-2">{{ error() }}</p>
      }

      @if (canEdit()) {
        <form
          [formGroup]="form"
          (ngSubmit)="crear()"
          class="mt-4 space-y-3 border-t pt-4"
          novalidate
        >
          <h3 class="text-xs font-black text-slate-500 uppercase">Nuevo plan</h3>
          <div class="grid gap-3 sm:grid-cols-3">
            <div>
              <label for="plan-nombre" class="label">Servicio</label>
              <input
                id="plan-nombre"
                formControlName="nombre"
                placeholder="Cambio de aceite"
                class="input"
              />
            </div>
            <div>
              <label for="plan-horas" class="label">Cada (horas)</label>
              <input
                id="plan-horas"
                type="number"
                min="0.1"
                step="0.1"
                formControlName="cada_horas"
                class="input"
              />
            </div>
            <div>
              <label for="plan-dias" class="label">Cada (días)</label>
              <input
                id="plan-dias"
                type="number"
                min="1"
                step="1"
                formControlName="cada_dias"
                class="input"
              />
            </div>
          </div>
          <p class="text-xs text-slate-500">
            Indica las horas, los días o ambos: avisa con lo que ocurra primero.
          </p>
          <button type="submit" class="btn-primary" [disabled]="!valido() || busy()">
            Agregar plan
          </button>
        </form>
      }
    </section>
  `,
})
export class EquipoMantenimiento implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly service = inject(MantenimientoService);

  readonly equipoId = input.required<string>();
  readonly canEdit = input.required<boolean>();

  protected readonly planes = signal<PlanMantenimiento[]>([]);
  protected readonly loaded = signal(false);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  /** Plan cuyo servicio se está registrando. */
  protected readonly hecho = signal<string | null>(null);

  protected readonly form = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(3)]],
    cada_horas: [null as number | null],
    cada_dias: [null as number | null],
  });
  protected readonly hechoForm = this.fb.group({ notas: [''] });

  ngOnInit(): void {
    this.load();
  }

  /** Hace falta el nombre y al menos un intervalo. */
  protected valido(): boolean {
    const v = this.form.getRawValue();
    return this.form.valid && (v.cada_horas !== null || v.cada_dias !== null);
  }

  protected crear(): void {
    if (!this.valido()) return;
    const v = this.form.getRawValue();
    this.run(
      this.service.crear(this.equipoId(), {
        nombre: v.nombre.trim(),
        cada_horas: v.cada_horas,
        cada_dias: v.cada_dias,
      }),
      'No se pudo crear el plan.',
      () => this.form.reset({ nombre: '', cada_horas: null, cada_dias: null }),
    );
  }

  protected registrarHecho(plan: PlanMantenimiento): void {
    const notas = this.hechoForm.getRawValue().notas.trim();
    this.run(
      this.service.realizado(plan.id, notas ? { notas } : {}),
      'No se pudo registrar el servicio.',
      () => {
        this.hecho.set(null);
        this.hechoForm.reset({ notas: '' });
      },
    );
  }

  protected borrar(plan: PlanMantenimiento): void {
    this.run(this.service.borrar(plan.id), 'No se pudo quitar el plan.');
  }

  private run(request: Observable<unknown>, failure: string, done?: () => void): void {
    this.busy.set(true);
    this.error.set(null);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        done?.();
        this.load();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err, failure));
      },
    });
  }

  private load(): void {
    this.service.planes(this.equipoId()).subscribe({
      next: (planes) => {
        this.planes.set(planes);
        this.loaded.set(true);
      },
      error: (err: unknown) => {
        this.loaded.set(true);
        this.error.set(apiErrorMessage(err, 'No se pudieron cargar los planes.'));
      },
    });
  }
}
