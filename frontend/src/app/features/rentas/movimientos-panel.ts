import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  OnInit,
  output,
  signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { apiErrorMessage } from '../../core/api/errors';
import { openBlob } from '../../core/api/download';
import { Movimientos, MovimientoTipo, Renta } from '../../core/api/models';
import { AuthService } from '../../core/auth/auth.service';
import { RentasService } from '../../core/rentas/rentas.service';

const TITULO: Record<MovimientoTipo, string> = {
  salida: 'Salida del equipo',
  regreso: 'Regreso del equipo',
};

/**
 * Salida y regreso del equipo con la lectura del horómetro y una foto del tablero. El personal
 * registra la salida de una renta confirmada y el regreso de una en curso; el cliente solo ve.
 */
@Component({
  selector: 'app-movimientos-panel',
  imports: [DatePipe, DecimalPipe, ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (data(); as m) {
      <section class="card mt-4" aria-labelledby="mov-titulo">
        <h2 id="mov-titulo" class="text-sm font-black">Entrega y devolución</h2>
        @if (error()) {
          <p role="alert" class="alert-error mt-2">{{ error() }}</p>
        }

        <ul class="mt-3 divide-y text-sm" aria-label="Movimientos">
          @for (mov of m.movimientos; track mov.id) {
            <li class="py-2" [attr.data-movimiento]="mov.tipo">
              <p class="font-semibold">{{ titulo[mov.tipo] }}</p>
              <p class="text-xs text-slate-500">
                Horómetro {{ mov.horometro | number: '1.1-1' }} h ·
                {{ mov.created_at | date: 'dd/MM/yyyy HH:mm' }} · {{ mov.registrado_por_nombre }}
              </p>
              @if (mov.notas) {
                <p class="text-xs">{{ mov.notas }}</p>
              }
              <button type="button" class="link text-xs" (click)="verFoto(mov.id)">
                Ver foto del tablero
              </button>
            </li>
          } @empty {
            <li class="py-2 text-slate-500">El equipo todavía no sale.</li>
          }
        </ul>
        @if (m.horas_usadas !== null) {
          <p class="mt-2 text-sm" data-testid="horas-usadas">
            Horas marcadas por el equipo: <strong>{{ m.horas_usadas | number: '1.1-1' }} h</strong>
          </p>
        }

        @if (pendiente(); as tipo) {
          <form
            [formGroup]="form"
            (ngSubmit)="registrar(tipo)"
            class="mt-4 grid gap-3 border-t pt-4 sm:grid-cols-2"
            novalidate
          >
            <h3 class="text-xs font-black text-slate-500 uppercase sm:col-span-2">
              Registrar {{ tipo === 'salida' ? 'la salida' : 'el regreso' }}
            </h3>
            <div>
              <label for="mov-horometro" class="label">Horómetro (h)</label>
              <input
                id="mov-horometro"
                type="number"
                step="0.1"
                min="0"
                formControlName="horometro"
                class="input"
              />
            </div>
            <div>
              <label for="mov-foto" class="label">Foto del tablero</label>
              <input
                id="mov-foto"
                type="file"
                accept="image/*"
                class="input"
                (change)="foto.set($any($event.target).files?.[0] ?? null)"
              />
            </div>
            <div class="sm:col-span-2">
              <label for="mov-notas" class="label">Notas (opcional)</label>
              <input id="mov-notas" formControlName="notas" class="input" maxlength="300" />
            </div>
            <div class="sm:col-span-2">
              <button
                type="submit"
                class="btn-primary"
                [disabled]="form.invalid || !foto() || busy()"
              >
                {{ tipo === 'salida' ? 'Registrar salida' : 'Registrar regreso' }}
              </button>
            </div>
          </form>
        }
      </section>
    }
  `,
})
export class MovimientosPanel implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly service = inject(RentasService);
  private readonly auth = inject(AuthService);

  readonly renta = input.required<Renta>();
  /** Avisa que cambió el estado de la renta, para que la pantalla lo refresque. */
  readonly changed = output<void>();

  protected readonly titulo = TITULO;
  protected readonly data = signal<Movimientos | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly busy = signal(false);
  protected readonly foto = signal<File | null>(null);

  protected readonly form = this.fb.group({
    horometro: [0, [Validators.required, Validators.min(0)]],
    notas: [''],
  });

  /** Lo que el personal puede registrar ahora, según el estado de la renta. */
  protected readonly pendiente = computed<MovimientoTipo | null>(() => {
    if (this.auth.user()?.role === 'cliente') return null;
    const estado = this.renta().estado;
    if (estado === 'confirmada') return 'salida';
    return estado === 'en_renta' ? 'regreso' : null;
  });

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.service.movimientos(this.renta().id).subscribe({
      next: (m) => this.data.set(m),
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'No se pudieron cargar los movimientos.')),
    });
  }

  protected registrar(tipo: MovimientoTipo): void {
    const foto = this.foto();
    if (this.form.invalid || !foto) return;
    const v = this.form.getRawValue();
    this.busy.set(true);
    this.error.set(null);
    this.service
      .registrarMovimiento(
        this.renta().id,
        { tipo, horometro: v.horometro, notas: v.notas.trim() },
        foto,
      )
      .subscribe({
        next: () => {
          this.busy.set(false);
          this.foto.set(null);
          this.form.reset({ horometro: v.horometro, notas: '' });
          this.reload();
          this.changed.emit();
        },
        error: (err: unknown) => {
          this.busy.set(false);
          this.error.set(apiErrorMessage(err, 'No se pudo registrar el movimiento.'));
        },
      });
  }

  protected verFoto(movimientoId: string): void {
    this.service.fotoMovimiento(this.renta().id, movimientoId).subscribe({
      next: openBlob,
      error: (err: unknown) => this.error.set(apiErrorMessage(err, 'No se pudo abrir la foto.')),
    });
  }
}
