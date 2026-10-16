import { CurrencyPipe, DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable, tap } from 'rxjs';
import { apiErrorMessage } from '../../../core/api/errors';
import { Gasto, GastoCategoria } from '../../../core/api/models';
import { pagedList } from '../../../core/api/paged-list';
import { AuthService } from '../../../core/auth/auth.service';
import { Icon } from '../../../shared/icon/icon';
import { GastosService } from './gastos.service';

const PAGE_SIZE = 25;

const CATEGORIAS: { value: GastoCategoria; label: string; classes: string }[] = [
  { value: 'combustible', label: 'Combustible', classes: 'bg-amber-50 text-amber-700' },
  { value: 'mantenimiento', label: 'Mantenimiento', classes: 'bg-sky-50 text-sky-700' },
  { value: 'refacciones', label: 'Refacciones', classes: 'bg-violet-50 text-violet-700' },
  { value: 'operador', label: 'Operador', classes: 'bg-emerald-50 text-emerald-700' },
  { value: 'flete', label: 'Flete', classes: 'bg-orange-50 text-orange-700' },
  { value: 'otro', label: 'Otros', classes: 'bg-slate-100 text-slate-600' },
];

/** Gastos del negocio: con ellos y lo cobrado se calcula la ganancia del mes. */
@Component({
  selector: 'app-gastos-page',
  imports: [CurrencyPipe, DatePipe, ReactiveFormsModule, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="page-title">Gastos</h1>
        <p class="page-subtitle">
          Lo que sale del negocio. Se resta de lo cobrado para calcular la ganancia.
        </p>
      </div>
      <div class="card flex items-center gap-3 !py-3">
        <span class="grid size-10 place-items-center rounded-xl bg-rose-100 text-rose-600">
          <app-icon name="gastos" class="size-5" />
        </span>
        <div>
          <p class="text-xs text-slate-500">Total de esta lista</p>
          <p class="text-xl font-extrabold" data-testid="suma">
            {{ suma() | currency: 'MXN' : 'symbol-narrow' : '1.0-2' }}
          </p>
        </div>
      </div>
    </div>

    @if (aviso()) {
      <p role="status" class="alert-ok mt-4">{{ aviso() }}</p>
    }
    @if (error() || list.error()) {
      <p role="alert" class="alert-error mt-4">{{ error() || list.error() }}</p>
    }

    <div class="mt-4 grid gap-3 sm:grid-cols-3">
      <div>
        <label for="g-mes" class="label">Mes</label>
        <input id="g-mes" type="month" [formControl]="mes" class="input" />
      </div>
      <div>
        <label for="g-cat" class="label">Categoría</label>
        <select id="g-cat" [formControl]="categoria" class="input">
          <option value="">Todas</option>
          @for (c of categorias; track c.value) {
            <option [value]="c.value">{{ c.label }}</option>
          }
        </select>
      </div>
    </div>

    <div class="table-card mt-4">
      <table class="w-full text-left text-sm">
        <thead class="table-head">
          <tr>
            <th class="px-4 py-3.5">Fecha</th>
            <th class="px-4 py-3.5">Concepto</th>
            <th class="px-4 py-3.5">Categoría</th>
            <th class="px-4 py-3.5">Equipo</th>
            <th class="px-4 py-3.5 text-right">Monto</th>
            @if (isAdmin()) {
              <th class="px-4 py-3.5"></th>
            }
          </tr>
        </thead>
        <tbody class="table-body">
          @for (g of list.items(); track g.id) {
            <tr [attr.data-gasto]="g.concepto">
              <td class="px-4 py-3.5 whitespace-nowrap text-slate-500">
                {{ g.fecha | date: 'dd/MM/yyyy' }}
              </td>
              <td class="px-4 py-3.5 font-semibold">{{ g.concepto }}</td>
              <td class="px-4 py-3.5">
                <span
                  class="rounded-full px-2.5 py-1 text-xs font-semibold"
                  [class]="estilo(g.categoria)"
                >
                  {{ etiqueta(g.categoria) }}
                </span>
              </td>
              <td class="px-4 py-3.5 text-slate-500">{{ g.equipo_codigo ?? '—' }}</td>
              <td class="px-4 py-3.5 text-right font-bold">
                {{ g.monto | currency: 'MXN' : 'symbol-narrow' : '1.0-2' }}
              </td>
              @if (isAdmin()) {
                <td class="px-4 py-3.5 text-right">
                  <button type="button" class="link text-rose-700" (click)="borrar(g)">
                    Borrar
                  </button>
                </td>
              }
            </tr>
          } @empty {
            <tr>
              <td [attr.colspan]="isAdmin() ? 6 : 5" class="p-8 text-center text-slate-500">
                {{ list.loaded() ? 'No hay gastos con esos filtros.' : 'Cargando…' }}
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>

    @if (list.pages() > 1) {
      <nav class="mt-4 flex items-center justify-between text-sm" aria-label="Paginación">
        <button
          type="button"
          class="btn-secondary"
          [disabled]="list.page() === 0"
          (click)="list.go(list.page() - 1)"
        >
          Anterior
        </button>
        <span>Página {{ list.page() + 1 }} de {{ list.pages() }}</span>
        <button
          type="button"
          class="btn-secondary"
          [disabled]="list.page() + 1 >= list.pages()"
          (click)="list.go(list.page() + 1)"
        >
          Siguiente
        </button>
      </nav>
    }

    @if (isAdmin()) {
      <form [formGroup]="form" (ngSubmit)="crear()" class="card mt-6 space-y-4" novalidate>
        <h2 class="font-bold text-slate-900">Registrar un gasto</h2>
        <div class="grid gap-4 sm:grid-cols-4">
          <div class="sm:col-span-2">
            <label for="n-concepto" class="label">Concepto</label>
            <input
              id="n-concepto"
              formControlName="concepto"
              class="input"
              placeholder="Diésel de la semana"
            />
          </div>
          <div>
            <label for="n-categoria" class="label">Categoría del gasto</label>
            <select id="n-categoria" formControlName="categoria" class="input">
              @for (c of categorias; track c.value) {
                <option [value]="c.value">{{ c.label }}</option>
              }
            </select>
          </div>
          <div>
            <label for="n-monto" class="label">Monto (MXN)</label>
            <input
              id="n-monto"
              type="number"
              min="0.01"
              step="0.01"
              formControlName="monto"
              class="input"
            />
          </div>
          <div>
            <label for="n-fecha" class="label">Fecha</label>
            <input id="n-fecha" type="date" formControlName="fecha" class="input" />
          </div>
        </div>
        <button type="submit" class="btn-primary" [disabled]="form.invalid || busy()">
          Registrar gasto
        </button>
      </form>
    }
  `,
})
export class GastosPage implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly service = inject(GastosService);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly categorias = CATEGORIAS;
  protected readonly mes = new FormControl('', { nonNullable: true });
  protected readonly categoria = new FormControl<'' | GastoCategoria>('', { nonNullable: true });
  protected readonly suma = signal(0);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly aviso = signal<string | null>(null);
  protected readonly isAdmin = computed(() => this.auth.user()?.role === 'admin');

  protected readonly list = pagedList<Gasto>({
    pageSize: PAGE_SIZE,
    fetch: (page) =>
      this.service
        .list({
          mes: this.mes.value || undefined,
          categoria: this.categoria.value || undefined,
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        })
        .pipe(tap((res) => this.suma.set(res.suma))),
    errorMessage: 'No se pudieron cargar los gastos.',
  });

  protected readonly form = this.fb.group({
    concepto: ['', [Validators.required, Validators.minLength(3)]],
    categoria: ['combustible' as GastoCategoria],
    monto: [0, [Validators.required, Validators.min(0.01)]],
    fecha: [new Date().toLocaleDateString('en-CA'), Validators.required],
  });

  ngOnInit(): void {
    this.mes.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.list.go(0));
    this.categoria.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.list.go(0));
    this.list.go(0);
  }

  protected etiqueta(c: GastoCategoria): string {
    return CATEGORIAS.find((x) => x.value === c)?.label ?? c;
  }

  protected estilo(c: GastoCategoria): string {
    return CATEGORIAS.find((x) => x.value === c)?.classes ?? '';
  }

  protected crear(): void {
    if (this.form.invalid) return;
    const v = this.form.getRawValue();
    this.run(
      this.service.create({
        concepto: v.concepto.trim(),
        categoria: v.categoria,
        monto: v.monto,
        fecha: v.fecha,
      }),
      'No se pudo registrar el gasto.',
      'Gasto registrado.',
      () => this.form.patchValue({ concepto: '', monto: 0 }),
    );
  }

  protected borrar(g: Gasto): void {
    this.run(this.service.delete(g.id), 'No se pudo borrar el gasto.', 'Gasto borrado.');
  }

  private run(request: Observable<unknown>, failure: string, ok: string, done?: () => void): void {
    this.busy.set(true);
    this.error.set(null);
    this.aviso.set(null);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.aviso.set(ok);
        done?.();
        this.list.go(this.list.page());
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err, failure));
      },
    });
  }
}
