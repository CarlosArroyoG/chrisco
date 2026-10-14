import { CurrencyPipe, DatePipe } from '@angular/common';
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
import { Observable } from 'rxjs';
import { apiErrorMessage } from '../../core/api/errors';
import { openBlob } from '../../core/api/download';
import { ChecklistItem, Cumplimiento, Renta, RevisionEstado } from '../../core/api/models';
import { AuthService } from '../../core/auth/auth.service';
import { RentasService } from '../../core/rentas/rentas.service';

const SITUACION: Record<ChecklistItem['situacion'], { label: string; classes: string }> = {
  pendiente: { label: 'Pendiente', classes: 'bg-amber-100 text-amber-800' },
  en_revision: { label: 'En revisión', classes: 'bg-sky-100 text-sky-800' },
  rechazado: { label: 'Rechazado', classes: 'bg-rose-100 text-rose-800' },
  cumplido: { label: 'Cumplido', classes: 'bg-emerald-100 text-emerald-800' },
};

const REVISION: Record<RevisionEstado, string> = {
  pendiente: 'Por revisar',
  aprobado: 'Aprobado',
  rechazado: 'Rechazado',
};

/** Una decisión de rechazo en curso: qué se rechaza y con qué motivo se pide. */
interface Rechazo {
  tipo: 'documento' | 'pago';
  id: string;
}

/**
 * Requisitos del apartado: el cliente sube documentos y reporta transferencias; el personal los
 * revisa y marca las condiciones. Cuando todo se cumple, el servidor confirma la renta solo.
 */
@Component({
  selector: 'app-cumplimiento-panel',
  imports: [CurrencyPipe, DatePipe, ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (data(); as c) {
      <section class="card mt-4" aria-labelledby="cumpl-titulo">
        <h2 id="cumpl-titulo" class="text-sm font-black">Cumplimiento y pagos</h2>
        @if (error()) {
          <p role="alert" class="alert-error mt-2">{{ error() }}</p>
        }
        @if (c.confirmada) {
          <p role="status" class="alert-ok mt-2">
            Renta confirmada: se cumplieron todos los requisitos.
          </p>
        }

        <dl class="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          <div>
            <dt class="label">Total</dt>
            <dd>{{ c.total | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}</dd>
          </div>
          <div>
            <dt class="label">Anticipo</dt>
            <dd>{{ c.anticipo_requerido | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}</dd>
          </div>
          <div>
            <dt class="label">Pagado</dt>
            <dd data-testid="pagado">
              {{ c.pagado | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}
            </dd>
          </div>
          <div>
            <dt class="label">Saldo</dt>
            <dd data-testid="saldo">{{ c.saldo | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}</dd>
          </div>
        </dl>

        <ul class="mt-4 divide-y text-sm">
          @for (item of c.checklist; track item.codigo) {
            <li class="py-3" [attr.data-requisito]="item.codigo">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p class="font-semibold">{{ item.titulo }}</p>
                  <p class="text-xs text-slate-500">{{ item.detalle }}</p>
                </div>
                <span
                  class="rounded-full px-2.5 py-0.5 text-[11px] font-bold"
                  [class]="situacion[item.situacion].classes"
                  >{{ situacion[item.situacion].label }}</span
                >
              </div>

              @if (item.tipo === 'documento') {
                <ul class="mt-2 space-y-1 text-xs">
                  @for (d of docsOf(item.codigo); track d.id) {
                    <li class="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <button type="button" class="link" (click)="verDocumento(d.id)">
                        {{ d.filename }}
                      </button>
                      <span>{{ revision[d.estado] }}</span>
                      @if (d.nota_revision) {
                        <span class="text-rose-700">{{ d.nota_revision }}</span>
                      }
                      @if (d.numero && d.vigente_hasta) {
                        <span class="text-slate-500">
                          Licencia {{ d.numero }}, vigente hasta
                          {{ d.vigente_hasta | date: 'dd/MM/yyyy' }}
                        </span>
                      }
                      @if (isStaff() && d.estado === 'pendiente') {
                        <button
                          type="button"
                          class="link"
                          [disabled]="busy()"
                          (click)="aprobarDocumento(d.id, item.codigo)"
                        >
                          Aprobar
                        </button>
                        <button
                          type="button"
                          class="link text-rose-700"
                          (click)="rechazo.set({ tipo: 'documento', id: d.id })"
                        >
                          Rechazar
                        </button>
                      }
                    </li>
                  }
                </ul>
                @if (canUpload()) {
                  <div class="mt-2">
                    <label class="btn-secondary inline-block cursor-pointer">
                      Subir archivo
                      <input
                        type="file"
                        class="sr-only"
                        accept="application/pdf,image/*"
                        [attr.aria-label]="'Subir ' + item.titulo"
                        (change)="subirDocumento(item.codigo, $event)"
                      />
                    </label>
                  </div>
                }
              } @else if (isStaff() && item.tipo === 'condicion' && item.codigo !== 'anticipo') {
                <label class="mt-2 flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    [checked]="item.situacion === 'cumplido'"
                    [disabled]="busy()"
                    (change)="marcar(item.codigo, $any($event.target).checked)"
                  />
                  Verificada
                </label>
              }
            </li>
          }
        </ul>

        @if (licencia()) {
          <form [formGroup]="licenciaForm" (ngSubmit)="confirmarLicencia()" class="mt-3 space-y-2">
            <p class="text-xs text-slate-500">
              Revisa la foto y captura lo que dice la licencia. Debe vencer después de que termine
              la renta.
            </p>
            <div class="grid gap-3 sm:grid-cols-2">
              <div>
                <label for="lic-numero" class="label">Número de licencia</label>
                <input id="lic-numero" formControlName="numero" class="input" maxlength="40" />
              </div>
              <div>
                <label for="lic-vigencia" class="label">Vigente hasta</label>
                <input
                  id="lic-vigencia"
                  type="date"
                  formControlName="vigente_hasta"
                  class="input"
                />
              </div>
            </div>
            <div class="flex gap-3">
              <button type="submit" class="btn-primary" [disabled]="licenciaForm.invalid || busy()">
                Aprobar licencia
              </button>
              <button type="button" class="link text-xs" (click)="licencia.set(null)">
                Cancelar
              </button>
            </div>
          </form>
        }

        @if (rechazo()) {
          <form [formGroup]="notaForm" (ngSubmit)="confirmarRechazo()" class="mt-3 space-y-2">
            <label for="rechazo-nota" class="label">Motivo del rechazo (le llega al cliente)</label>
            <input id="rechazo-nota" formControlName="nota" class="input" />
            <div class="flex gap-3">
              <button type="submit" class="btn-danger" [disabled]="notaForm.invalid || busy()">
                Confirmar rechazo
              </button>
              <button type="button" class="link text-xs" (click)="rechazo.set(null)">
                Cancelar
              </button>
            </div>
          </form>
        }

        <h3 class="mt-5 text-xs font-black text-slate-500 uppercase">Transferencias</h3>
        <ul class="mt-1 space-y-1 text-xs" aria-label="Transferencias">
          @for (p of c.pagos; track p.id) {
            <li class="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span class="font-semibold">
                {{ p.monto | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}
              </span>
              <span>{{ p.fecha_pago | date: 'dd/MM/yyyy' }}</span>
              @if (p.referencia) {
                <span class="text-slate-500">Ref. {{ p.referencia }}</span>
              }
              <button type="button" class="link" (click)="verComprobante(p.id)">Comprobante</button>
              <span>{{ revision[p.estado] }}</span>
              @if (p.nota_revision) {
                <span class="text-rose-700">{{ p.nota_revision }}</span>
              }
              @if (isStaff() && p.estado === 'pendiente') {
                <button
                  type="button"
                  class="link"
                  [disabled]="busy()"
                  (click)="revisarPago(p.id, true)"
                >
                  Confirmar pago
                </button>
                <button
                  type="button"
                  class="link text-rose-700"
                  (click)="rechazo.set({ tipo: 'pago', id: p.id })"
                >
                  Rechazar
                </button>
              }
            </li>
          } @empty {
            <li class="text-slate-500">Aún no hay transferencias.</li>
          }
        </ul>

        @if (canPay() && (c.saldo ?? 0) > 0) {
          <form
            [formGroup]="pagoForm"
            (ngSubmit)="reportarPago()"
            class="mt-4 grid gap-3 border-t pt-4 sm:grid-cols-2"
            novalidate
          >
            <p class="text-xs text-slate-500 sm:col-span-2">
              Haz la transferencia y repórtala aquí con su comprobante; ventas confirmará que el
              dinero llegó.
            </p>
            <div>
              <label for="pago-monto" class="label">Monto transferido (MXN)</label>
              <input
                id="pago-monto"
                type="number"
                step="0.01"
                min="0.01"
                formControlName="monto"
                class="input"
              />
            </div>
            <div>
              <label for="pago-fecha" class="label">Fecha de la transferencia</label>
              <input id="pago-fecha" type="date" formControlName="fecha_pago" class="input" />
            </div>
            <div>
              <label for="pago-ref" class="label">Referencia o rastreo (opcional)</label>
              <input id="pago-ref" formControlName="referencia" class="input" maxlength="80" />
            </div>
            <div>
              <label for="pago-archivo" class="label">Comprobante (PDF o foto)</label>
              <input
                id="pago-archivo"
                type="file"
                accept="application/pdf,image/*"
                class="input"
                (change)="comprobante.set($any($event.target).files?.[0] ?? null)"
              />
            </div>
            <div class="sm:col-span-2">
              <button
                type="submit"
                class="btn-primary"
                [disabled]="pagoForm.invalid || !comprobante() || busy()"
              >
                Reportar transferencia
              </button>
            </div>
          </form>
        }
      </section>
    }
  `,
})
export class CumplimientoPanel implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly service = inject(RentasService);
  private readonly auth = inject(AuthService);

  readonly renta = input.required<Renta>();
  /** Avisa que algo cambió, para que la pantalla refresque el estado de la renta. */
  readonly changed = output<void>();

  protected readonly situacion = SITUACION;
  protected readonly revision = REVISION;
  protected readonly data = signal<Cumplimiento | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly busy = signal(false);
  protected readonly rechazo = signal<Rechazo | null>(null);
  protected readonly comprobante = signal<File | null>(null);
  /** Id de la licencia que se está aprobando (pide número y vigencia). */
  protected readonly licencia = signal<string | null>(null);

  protected readonly isStaff = computed(() => this.auth.user()?.role !== 'cliente');
  protected readonly canUpload = computed(
    () => !this.isStaff() && this.renta().estado === 'apartada',
  );
  protected readonly canPay = computed(() => !this.isStaff());

  protected readonly notaForm = this.fb.group({
    nota: ['', [Validators.required, Validators.minLength(3)]],
  });
  protected readonly licenciaForm = this.fb.group({
    numero: ['', [Validators.required, Validators.minLength(3)]],
    vigente_hasta: ['', Validators.required],
  });
  protected readonly pagoForm = this.fb.group({
    monto: [0, [Validators.required, Validators.min(0.01)]],
    fecha_pago: [new Date().toLocaleDateString('en-CA'), Validators.required],
    referencia: [''],
  });

  ngOnInit(): void {
    this.reload();
  }

  protected docsOf(requisito: string) {
    return (this.data()?.documentos ?? []).filter((d) => d.requisito === requisito);
  }

  private reload(): void {
    this.service.cumplimiento(this.renta().id).subscribe({
      next: (c) => this.data.set(c),
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'No se pudo cargar el cumplimiento.')),
    });
  }

  /** Aplica el resultado de una acción; si la renta se confirmó, avisa al padre. */
  private run(request: ReturnType<RentasService['marcarCondicion']>, failure: string): void {
    this.busy.set(true);
    this.error.set(null);
    request.subscribe({
      next: (c) => {
        this.busy.set(false);
        const confirmed = c.confirmada && this.renta().estado === 'apartada';
        this.data.set(c);
        if (confirmed) this.changed.emit();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err, failure));
        this.reload();
      },
    });
  }

  /** Acción del cliente (subir/reportar): devuelve un registro, no el cumplimiento completo. */
  private after(request: Observable<unknown>, failure: string): void {
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
      },
    });
  }

  protected subirDocumento(requisito: string, event: Event): void {
    const input = event.target as HTMLInputElement;
    const archivo = input.files?.[0];
    if (!archivo) return;
    this.after(
      this.service.subirDocumento(this.renta().id, requisito, archivo),
      'No se pudo subir el archivo.',
    );
    input.value = '';
  }

  protected reportarPago(): void {
    const archivo = this.comprobante();
    if (this.pagoForm.invalid || !archivo) return;
    const v = this.pagoForm.getRawValue();
    this.after(
      this.service.reportarPago(
        this.renta().id,
        { monto: v.monto, fecha_pago: v.fecha_pago, referencia: v.referencia.trim() },
        archivo,
      ),
      'No se pudo reportar la transferencia.',
    );
    this.pagoForm.patchValue({ monto: 0, referencia: '' });
    this.comprobante.set(null);
  }

  protected verDocumento(docId: string): void {
    this.service.documento(this.renta().id, docId).subscribe({
      next: openBlob,
      error: (err: unknown) => this.error.set(apiErrorMessage(err, 'No se pudo abrir el archivo.')),
    });
  }

  protected verComprobante(pagoId: string): void {
    this.service.comprobante(this.renta().id, pagoId).subscribe({
      next: openBlob,
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'No se pudo abrir el comprobante.')),
    });
  }

  /** Una licencia no se aprueba a ciegas: primero se capturan su número y su vigencia. */
  protected aprobarDocumento(docId: string, requisito: string): void {
    if (requisito === 'licencia_federal') this.licencia.set(docId);
    else this.revisarDocumento(docId, true);
  }

  protected confirmarLicencia(): void {
    const docId = this.licencia();
    if (!docId || this.licenciaForm.invalid) return;
    const datos = this.licenciaForm.getRawValue();
    this.licencia.set(null);
    this.licenciaForm.reset();
    this.revisarDocumento(docId, true, undefined, {
      numero: datos.numero.trim(),
      vigente_hasta: datos.vigente_hasta,
    });
  }

  protected revisarDocumento(
    docId: string,
    aprobado: boolean,
    nota?: string,
    licencia?: { numero: string; vigente_hasta: string },
  ): void {
    this.run(
      this.service.revisarDocumento(this.renta().id, docId, aprobado, nota, licencia),
      'No se pudo revisar el documento.',
    );
  }

  protected revisarPago(pagoId: string, aprobado: boolean, nota?: string): void {
    this.run(
      this.service.revisarPago(this.renta().id, pagoId, aprobado, nota),
      'No se pudo revisar el pago.',
    );
  }

  protected marcar(codigo: string, cumplida: boolean): void {
    this.run(
      this.service.marcarCondicion(this.renta().id, codigo, cumplida),
      'No se pudo marcar la condición.',
    );
  }

  protected confirmarRechazo(): void {
    const actual = this.rechazo();
    if (!actual || this.notaForm.invalid) return;
    const nota = this.notaForm.getRawValue().nota.trim();
    this.rechazo.set(null);
    this.notaForm.reset();
    if (actual.tipo === 'documento') this.revisarDocumento(actual.id, false, nota);
    else this.revisarPago(actual.id, false, nota);
  }
}
