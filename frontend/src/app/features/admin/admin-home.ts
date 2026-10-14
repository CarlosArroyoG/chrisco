import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
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
    <h1 class="text-lg font-black">Empresas clientes</h1>
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

    <div class="mt-3 overflow-x-auto rounded-xl border bg-white">
      <table class="w-full text-left text-xs">
        <thead class="bg-chrisco-charcoal text-[10px] font-bold text-white uppercase">
          <tr>
            <th class="p-3">Empresa</th>
            <th class="p-3">RFC</th>
            <th class="p-3">Titular</th>
            <th class="p-3">Registro</th>
            <th class="p-3">Estado</th>
            <th class="p-3"></th>
          </tr>
        </thead>
        <tbody class="divide-y">
          @for (e of empresas(); track e.id) {
            <tr>
              <td class="p-3 font-semibold">{{ e.razon_social }}</td>
              <td class="p-3 font-mono">{{ e.rfc }}</td>
              <td class="p-3">
                {{ e.owner_name }}<br /><span class="text-slate-500">{{ e.owner_email }}</span>
              </td>
              <td class="p-3">{{ e.created_at | date: 'dd/MM/yyyy' }}</td>
              <td class="p-3"><app-status-badge [status]="e.status" /></td>
              <td class="p-3">
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

  protected readonly filters = FILTERS;
  protected readonly filter = signal<EmpresaStatus | undefined>('pendiente');
  protected readonly empresas = signal<EmpresaListItem[]>([]);
  protected readonly loaded = signal(false);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  protected select(status: EmpresaStatus | undefined): void {
    this.filter.set(status);
    this.load();
  }

  private load(): void {
    this.loaded.set(false);
    this.error.set(null);
    this.service.list(this.filter()).subscribe({
      next: (list) => {
        this.empresas.set(list);
        this.loaded.set(true);
      },
      error: (err: unknown) => {
        this.loaded.set(true);
        this.error.set(apiErrorMessage(err, 'No se pudo cargar la lista de empresas.'));
      },
    });
  }
}
