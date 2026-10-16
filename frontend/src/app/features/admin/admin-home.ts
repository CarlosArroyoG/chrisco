import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { catchError, of, Subject, switchMap, tap } from 'rxjs';
import { apiErrorMessage } from '../../core/api/errors';
import { EmpresaListItem, EmpresaStatus } from '../../core/api/models';
import { StatusBadge } from '../../shared/status-badge/status-badge';
import { AdminEmpresasService } from './admin-empresas.service';

const FILTERS: { value: EmpresaStatus | undefined; label: string }[] = [
  { value: 'pendiente', label: 'Pendientes' },
  { value: 'aprobada', label: 'Aprobadas' },
  { value: 'rechazada', label: 'Rechazadas' },
  { value: undefined, label: 'Todas' },
];

/** Inicio del personal: empresas por revisar. Las rentas, equipos y cobranza llegan en fases siguientes. */
@Component({
  selector: 'app-admin-home',
  imports: [DatePipe, RouterLink, StatusBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1 class="page-title">Empresas clientes</h1>
    <div class="mt-3 flex flex-wrap gap-2" role="tablist">
      @for (f of filters; track f.label) {
        <button
          type="button"
          role="tab"
          [attr.aria-selected]="f.value === filter()"
          (click)="select(f.value)"
          class="rounded-full px-3 py-1 text-xs font-bold"
          [class]="
            f.value === filter()
              ? 'bg-chrisco-charcoal text-white'
              : 'border border-slate-300 bg-white text-slate-600'
          "
        >
          {{ f.label }}
        </button>
      }
    </div>

    @if (error()) {
      <p role="alert" class="alert-error mt-3">{{ error() }}</p>
    }

    <div class="table-card mt-4">
      <table class="w-full text-left text-sm">
        <thead class="table-head">
          <tr>
            <th class="px-4 py-3.5">Empresa</th>
            <th class="px-4 py-3.5">RFC</th>
            <th class="px-4 py-3.5">Titular</th>
            <th class="px-4 py-3.5">Registro</th>
            <th class="px-4 py-3.5">Estado</th>
            <th class="px-4 py-3.5"></th>
          </tr>
        </thead>
        <tbody class="table-body">
          @for (e of empresas(); track e.id) {
            <tr>
              <td class="px-4 py-3.5 font-semibold">{{ e.razon_social }}</td>
              <td class="px-4 py-3.5 font-mono">{{ e.rfc }}</td>
              <td class="px-4 py-3.5">
                {{ e.owner_name }}<br /><span class="text-slate-500">{{ e.owner_email }}</span>
              </td>
              <td class="px-4 py-3.5">{{ e.created_at | date: 'dd/MM/yyyy' }}</td>
              <td class="px-4 py-3.5"><app-status-badge [status]="e.status" /></td>
              <td class="px-4 py-3.5">
                <a [routerLink]="['/admin/empresas', e.id]" class="link">Revisar</a>
              </td>
            </tr>
          } @empty {
            <tr>
              <td colspan="6" class="p-6 text-center text-slate-500">
                {{ loaded() ? 'No hay empresas en esta lista.' : 'Cargando…' }}
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  `,
})
export class AdminHome implements OnInit {
  private readonly service = inject(AdminEmpresasService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly filters = FILTERS;
  protected readonly filter = signal<EmpresaStatus | undefined>('pendiente');
  protected readonly empresas = signal<EmpresaListItem[]>([]);
  protected readonly loaded = signal(false);
  protected readonly error = signal<string | null>(null);

  /** Cada consulta cancela a la anterior: una respuesta vieja no pisa a la nueva. */
  private readonly load$ = new Subject<EmpresaStatus | undefined>();

  ngOnInit(): void {
    this.load$
      .pipe(
        tap(() => {
          this.loaded.set(false);
          this.error.set(null);
        }),
        switchMap((status) =>
          this.service.list(status).pipe(
            catchError((err: unknown) => {
              this.error.set(apiErrorMessage(err, 'No se pudo cargar la lista de empresas.'));
              return of(null);
            }),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((list) => {
        if (list) this.empresas.set(list);
        this.loaded.set(true);
      });
    this.load$.next(this.filter());
  }

  protected select(status: EmpresaStatus | undefined): void {
    this.filter.set(status);
    this.load$.next(status);
  }
}
