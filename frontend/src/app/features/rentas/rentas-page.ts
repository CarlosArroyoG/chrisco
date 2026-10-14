import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  inject,
  OnInit,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { debounceTime, distinctUntilChanged } from 'rxjs';
import { Renta, RentaEstado } from '../../core/api/models';
import { pagedList } from '../../core/api/paged-list';
import { AuthService } from '../../core/auth/auth.service';
import { RentasService } from '../../core/rentas/rentas.service';
import { StatusBadge } from '../../shared/status-badge/status-badge';

const PAGE_SIZE = 25;

const ESTADOS: { value: RentaEstado; label: string }[] = [
  { value: 'solicitada', label: 'Solicitadas' },
  { value: 'cotizada', label: 'Cotizadas' },
  { value: 'apartada', label: 'Apartadas' },
  { value: 'confirmada', label: 'Confirmadas' },
  { value: 'en_renta', label: 'En renta' },
  { value: 'devuelta', label: 'Devueltas' },
  { value: 'cerrada', label: 'Cerradas' },
  { value: 'vencida', label: 'Vencidas' },
  { value: 'cancelada', label: 'Canceladas' },
];

/** Rentas: el cliente ve las de su empresa; el personal, todas. */
@Component({
  selector: 'app-rentas-page',
  imports: [DatePipe, ReactiveFormsModule, RouterLink, StatusBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (!isStaff()) {
      <a routerLink="/cliente" class="link text-xs">← Mi empresa</a>
    }
    <h1 class="mt-2 text-lg font-black">
      {{ isStaff() ? 'Rentas' : 'Mis rentas' }} ({{ list.total() }})
    </h1>

    <div class="mt-3 grid gap-2 sm:grid-cols-3">
      <input
        type="search"
        [formControl]="q"
        [placeholder]="
          isStaff() ? 'Buscar por folio, empresa o equipo…' : 'Buscar por folio o equipo…'
        "
        aria-label="Buscar"
        class="input sm:col-span-2"
      />
      <select [formControl]="estado" aria-label="Estado" class="input">
        <option value="">Todos los estados</option>
        @for (e of estados; track e.value) {
          <option [value]="e.value">{{ e.label }}</option>
        }
      </select>
    </div>

    @if (list.error()) {
      <p role="alert" class="alert-error mt-3">{{ list.error() }}</p>
    }

    <div class="mt-3 overflow-x-auto rounded-xl border bg-white">
      <table class="w-full text-left text-xs">
        <thead class="bg-chrisco-charcoal text-[10px] font-bold text-white uppercase">
          <tr>
            <th class="p-3">Folio</th>
            @if (isStaff()) {
              <th class="p-3">Empresa</th>
            }
            <th class="p-3">Equipo</th>
            <th class="p-3">Periodo</th>
            <th class="p-3">Estado</th>
            <th class="p-3"></th>
          </tr>
        </thead>
        <tbody class="divide-y">
          @for (r of list.items(); track r.id) {
            <tr>
              <td class="p-3 font-mono font-bold">{{ r.folio }}</td>
              @if (isStaff()) {
                <td class="p-3">{{ r.empresa_razon_social }}</td>
              }
              <td class="p-3">
                <span class="font-semibold">{{ r.equipo_nombre }}</span
                ><br />
                <span class="text-slate-500">{{ r.equipo_codigo }}</span>
              </td>
              <td class="p-3">
                {{ r.desde | date: 'dd/MM/yy HH:mm' }} → {{ r.hasta | date: 'dd/MM/yy HH:mm' }}
              </td>
              <td class="p-3"><app-status-badge [status]="r.estado" /></td>
              <td class="p-3">
                <a [routerLink]="[basePath(), r.id]" class="link">Ver</a>
              </td>
            </tr>
          } @empty {
            <tr>
              <td [attr.colspan]="isStaff() ? 6 : 5" class="p-6 text-center text-slate-500">
                {{ list.loaded() ? 'No hay rentas con esos filtros.' : 'Cargando…' }}
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>

    @if (list.pages() > 1) {
      <nav class="mt-3 flex items-center justify-between text-xs" aria-label="Paginación">
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
  `,
})
export class RentasPage implements OnInit {
  private readonly service = inject(RentasService);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly estados = ESTADOS;
  protected readonly q = new FormControl('', { nonNullable: true });
  protected readonly estado = new FormControl<'' | RentaEstado>('', { nonNullable: true });
  protected readonly isStaff = computed(() => this.auth.user()?.role !== 'cliente');
  /** Ruta base de los detalles: cada rol tiene la suya. */
  protected readonly basePath = computed(() =>
    this.isStaff() ? '/admin/rentas' : '/cliente/rentas',
  );
  protected readonly list = pagedList<Renta>({
    pageSize: PAGE_SIZE,
    fetch: (page) =>
      this.service.list({
        q: this.q.value.trim(),
        estado: this.estado.value || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    errorMessage: 'No se pudo cargar la lista de rentas.',
  });

  ngOnInit(): void {
    this.q.valueChanges
      .pipe(debounceTime(300), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.list.go(0));
    this.estado.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.list.go(0));
    this.list.go(0);
  }
}
