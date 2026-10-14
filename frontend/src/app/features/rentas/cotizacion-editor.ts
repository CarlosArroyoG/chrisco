import { CurrencyPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  input,
  OnInit,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormArray, FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { catchError, debounceTime, of, switchMap } from 'rxjs';
import { apiErrorMessage } from '../../core/api/errors';
import {
  CotizacionInput,
  CotizacionSugerida,
  PartidaConcepto,
  PartidaInput,
  PartidaUnidad,
  Renta,
} from '../../core/api/models';
import { RentasService } from '../../core/rentas/rentas.service';
import { UNIDAD_LABEL } from './cotizacion-view';

const CONCEPTO_LABEL: Record<PartidaConcepto, string> = {
  renta: 'Renta',
  flete: 'Flete',
  trailer: 'Tractocamión adicional',
  combustible: 'Combustible',
  operador: 'Operador',
  seguro: 'Seguro',
  otro: 'Otro',
};

/** Ventas arma la cotización: parte de lo sugerido y ve los totales en vivo. */
@Component({
  selector: 'app-cotizacion-editor',
  imports: [CurrencyPipe, ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <form [formGroup]="form" (ngSubmit)="submit()" class="space-y-3" novalidate>
      <div class="space-y-2" formArrayName="partidas">
        @for (row of rows.controls; track row; let i = $index) {
          <div
            [formGroupName]="i"
            class="grid items-end gap-2 rounded-lg border p-2 sm:grid-cols-12"
          >
            <div class="sm:col-span-2">
              <label [for]="'p-concepto-' + i" class="label">Concepto</label>
              <select [id]="'p-concepto-' + i" formControlName="concepto" class="input">
                @for (c of conceptos; track c) {
                  <option [value]="c">{{ conceptoLabel[c] }}</option>
                }
              </select>
            </div>
            <div class="sm:col-span-4">
              <label [for]="'p-desc-' + i" class="label">Descripción</label>
              <input [id]="'p-desc-' + i" formControlName="descripcion" class="input" />
            </div>
            <div class="sm:col-span-1">
              <label [for]="'p-cant-' + i" class="label">Cant.</label>
              <input
                [id]="'p-cant-' + i"
                type="number"
                step="0.01"
                min="0.01"
                formControlName="cantidad"
                class="input"
              />
            </div>
            <div class="sm:col-span-1">
              <label [for]="'p-unidad-' + i" class="label">Unidad</label>
              <select [id]="'p-unidad-' + i" formControlName="unidad" class="input">
                @for (u of unidades; track u) {
                  <option [value]="u">{{ unidadLabel[u] }}</option>
                }
              </select>
            </div>
            <div class="sm:col-span-2">
              <label [for]="'p-precio-' + i" class="label">Precio unitario</label>
              <input
                [id]="'p-precio-' + i"
                type="number"
                step="0.01"
                min="0"
                formControlName="precio_unitario"
                class="input"
              />
            </div>
            <div class="text-right text-sm font-semibold sm:col-span-1">
              {{ importe(i) | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}
            </div>
            <div class="sm:col-span-1 sm:text-right">
              <button type="button" class="link text-xs text-rose-700" (click)="removeRow(i)">
                Quitar
              </button>
            </div>
          </div>
        }
        <button type="button" class="btn-secondary" (click)="addRow()">+ Agregar renglón</button>
      </div>

      <div class="grid gap-3 sm:grid-cols-3">
        <div>
          <label for="cot-anticipo" class="label">
            Anticipo (vacío = {{ sugerida()?.anticipo_default_percent }} % del total)
          </label>
          <input
            id="cot-anticipo"
            type="number"
            step="0.01"
            min="0"
            formControlName="anticipo"
            class="input"
          />
        </div>
        <div>
          <label for="cot-valida" class="label">Vigencia (horas)</label>
          <input
            id="cot-valida"
            type="number"
            min="1"
            max="168"
            formControlName="valida_horas"
            class="input"
          />
        </div>
        <div>
          <label for="cot-notas" class="label">Notas para el cliente</label>
          <input id="cot-notas" formControlName="notas" class="input" />
        </div>
      </div>

      @if (calculo(); as c) {
        <dl class="ml-auto grid max-w-xs grid-cols-2 gap-y-1 text-sm" aria-label="Totales">
          <dt class="text-slate-500">Subtotal</dt>
          <dd class="text-right">{{ c.subtotal | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}</dd>
          <dt class="text-slate-500">IVA ({{ ivaPercent() }} %)</dt>
          <dd class="text-right">{{ c.iva | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}</dd>
          <dt class="font-black">Total</dt>
          <dd class="text-right font-black">
            {{ c.total | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}
          </dd>
          <dt class="text-slate-500">Anticipo</dt>
          <dd class="text-right font-semibold">
            {{ c.anticipo_monto | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}
          </dd>
        </dl>
      }

      @if (error()) {
        <p role="alert" class="alert-error">{{ error() }}</p>
      }
      <button type="submit" class="btn-primary" [disabled]="form.invalid || busy()">
        {{ busy() ? 'Enviando…' : 'Enviar cotización al cliente' }}
      </button>
    </form>
  `,
})
export class CotizacionEditor implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly service = inject(RentasService);
  private readonly destroyRef = inject(DestroyRef);

  readonly renta = input.required<Renta>();
  /** Se emite al guardar la cotización. */
  readonly quoted = output<void>();

  protected readonly conceptos = Object.keys(CONCEPTO_LABEL) as PartidaConcepto[];
  protected readonly unidades = Object.keys(UNIDAD_LABEL) as PartidaUnidad[];
  protected readonly conceptoLabel = CONCEPTO_LABEL;
  protected readonly unidadLabel = UNIDAD_LABEL;

  protected readonly sugerida = signal<CotizacionSugerida | null>(null);
  protected readonly calculo = signal<{
    importes: number[];
    subtotal: number;
    iva: number;
    total: number;
    anticipo_monto: number;
  } | null>(null);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly rows = new FormArray<FormGroup>([]);
  protected readonly form = this.fb.group({
    partidas: this.rows,
    anticipo: [null as number | null],
    valida_horas: [null as number | null],
    notas: [''],
  });

  ngOnInit(): void {
    this.service.sugerida(this.renta().id).subscribe({
      next: (sugerida) => {
        this.sugerida.set(sugerida);
        sugerida.partidas.forEach((p) => this.addRow(p));
        this.form.controls.valida_horas.setValue(sugerida.valida_horas);
      },
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'No se pudo cargar la sugerencia.')),
    });

    // Los totales los calcula el servidor con la misma aritmética que al guardar.
    this.form.valueChanges
      .pipe(
        debounceTime(300),
        switchMap(() => {
          if (this.form.invalid) return of(null);
          return this.service.calcular(this.renta().id, this.payload()).pipe(
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err, 'No se pudo calcular la cotización.'));
              return of(null);
            }),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((calculo) => {
        if (calculo) this.error.set(null);
        this.calculo.set(calculo);
      });
  }

  protected ivaPercent(): number {
    return Math.round((this.sugerida()?.iva_rate ?? 0) * 100);
  }

  protected importe(index: number): number {
    return this.calculo()?.importes[index] ?? 0;
  }

  protected addRow(partida?: Partial<PartidaInput>): void {
    this.rows.push(
      this.fb.group({
        concepto: [partida?.concepto ?? ('otro' as PartidaConcepto)],
        descripcion: [partida?.descripcion ?? '', [Validators.required, Validators.minLength(3)]],
        cantidad: [Number(partida?.cantidad ?? 1), [Validators.required, Validators.min(0.01)]],
        unidad: [partida?.unidad ?? ('servicio' as PartidaUnidad)],
        precio_unitario: [
          Number(partida?.precio_unitario ?? 0),
          [Validators.required, Validators.min(0)],
        ],
      }),
    );
  }

  protected removeRow(index: number): void {
    this.rows.removeAt(index);
  }

  private payload(): CotizacionInput {
    const { anticipo, valida_horas, notas } = this.form.getRawValue();
    return {
      partidas: this.rows.getRawValue() as PartidaInput[],
      anticipo_monto: anticipo,
      valida_horas,
      notas: notas.trim() || null,
    };
  }

  protected submit(): void {
    if (this.form.invalid || !this.rows.length) {
      this.error.set('Agrega al menos un renglón y completa sus datos.');
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    this.service.cotizar(this.renta().id, this.payload()).subscribe({
      next: () => {
        this.busy.set(false);
        this.quoted.emit();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err, 'No se pudo enviar la cotización.'));
      },
    });
  }
}
