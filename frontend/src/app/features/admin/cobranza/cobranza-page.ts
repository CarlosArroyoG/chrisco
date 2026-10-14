import { CurrencyPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { debounceTime, distinctUntilChanged, tap } from 'rxjs';
import { Cobranza, CobranzaItem } from '../../../core/api/models';
import { pagedList } from '../../../core/api/paged-list';
import { RentasService } from '../../../core/rentas/rentas.service';
import { StatusBadge } from '../../../shared/status-badge/status-badge';

const PAGE_SIZE = 25;

/** Cobranza para los dueños: cuánto se cotizó, cuánto se ha confirmado y cuánto falta. */
@Component({
  selector: 'app-cobranza-page',
  imports: [CurrencyPipe, ReactiveFormsModule, RouterLink, StatusBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1 class="text-lg font-black">Cobranza</h1>

    @if (resumen(); as s) {
      <dl class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Resumen de cobranza">
        <div class="card">
          <dt class="label">Cotizado</dt>
          <dd class="font-black" data-testid="total-cotizado">
            {{ s.total_cotizado | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}
          </dd>
        </div>
        <div class="card">
          <dt class="label">Cobrado</dt>
          <dd class="font-black" data-testid="total-pagado">
            {{ s.total_pagado | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}
          </dd>
        </div>
        <div class="card">
          <dt class="label">Por cobrar</dt>
          <dd class="font-black" data-testid="total-saldo">
            {{ s.saldo | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}
          </dd>
        </div>
        <div class="card">
          <dt class="label">Pagos por confirmar</dt>
          <dd class="font-black" data-testid="por-confirmar">{{ s.pagos_por_confirmar }}</dd>
        </div>
      </dl>
    }

    <div class="mt-3 grid gap-2 sm:grid-cols-3">
      <input
        type="search"
        [formControl]="q"
        placeholder="Buscar por folio, empresa o equipo…"
        aria-label="Buscar"
        class="input sm:col-span-2"
      />
      <label class="flex items-center gap-2 text-xs">
        <input type="checkbox" [formControl]="soloSaldo" />
        Solo con saldo pendiente
      </label>
    </div>

    @if (list.error()) {
      <p role="alert" class="alert-error mt-3">{{ list.error() }}</p>
    }

    <div class="mt-3 overflow-x-auto rounded-xl border bg-white">
      <table class="w-full text-left text-xs">
        <thead class="bg-chrisco-charcoal text-[10px] font-bold text-white uppercase">
          <tr>
            <th class="p-3">Folio</th>
            <th class="p-3">Empresa</th>
            <th class="p-3">Equipo</th>
            <th class="p-3">Estado</th>
            <th class="p-3 text-right">Total</th>
            <th class="p-3 text-right">Pagado</th>
            <th class="p-3 text-right">Saldo</th>
            <th class="p-3"></th>
          </tr>
        </thead>
        <tbody class="divide-y">
          @for (r of list.items(); track r.renta_id) {
            <tr>
              <td class="p-3 font-mono font-bold">{{ r.folio }}</td>
              <td class="p-3">{{ r.empresa }}</td>
              <td class="p-3">{{ r.equipo }}</td>
              <td class="p-3"><app-status-badge [status]="r.estado" /></td>
              <td class="p-3 text-right">
                {{ r.total | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}
              </td>
              <td class="p-3 text-right">
                {{ r.pagado | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}
              </td>
              <td class="p-3 text-right font-bold">
                {{ r.saldo | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}
              </td>
              <td class="p-3">
                <a [routerLink]="['/admin/rentas', r.renta_id]" class="link">Ver</a>
              </td>
            </tr>
          } @empty {
            <tr>
              <td colspan="8" class="p-6 text-center text-slate-500">
                {{ list.loaded() ? 'No hay rentas por cobrar con esos filtros.' : 'Cargando…' }}
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
export class CobranzaPage implements OnInit {
  private readonly service = inject(RentasService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly q = new FormControl('', { nonNullable: true });
  protected readonly soloSaldo = new FormControl(false, { nonNullable: true });
  protected readonly resumen = signal<Cobranza['resumen'] | null>(null);
  protected readonly list = pagedList<CobranzaItem>({
    pageSize: PAGE_SIZE,
    fetch: (page) =>
      this.service
        .cobranza({
          q: this.q.value.trim(),
          solo_con_saldo: this.soloSaldo.value || undefined,
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        })
        .pipe(tap((cobranza) => this.resumen.set(cobranza.resumen))),
    errorMessage: 'No se pudo cargar la cobranza.',
  });

  ngOnInit(): void {
    this.q.valueChanges
      .pipe(debounceTime(300), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.list.go(0));
    this.soloSaldo.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.list.go(0));
    this.list.go(0);
  }
}
