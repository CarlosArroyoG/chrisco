import { CurrencyPipe, DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { Cotizacion, PartidaUnidad } from '../../core/api/models';

export const UNIDAD_LABEL: Record<PartidaUnidad, string> = {
  hora: 'hora',
  dia: 'día',
  viaje: 'viaje',
  litro: 'litro',
  servicio: 'servicio',
};

/** Cotización en solo lectura: renglones, totales y anticipo. */
@Component({
  selector: 'app-cotizacion-view',
  imports: [CurrencyPipe, DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (cotizacion(); as c) {
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead class="text-[10px] font-bold text-slate-500 uppercase">
            <tr>
              <th class="py-1">Concepto</th>
              <th class="py-1 text-right">Cantidad</th>
              <th class="py-1 text-right">Precio</th>
              <th class="py-1 text-right">Importe</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            @for (p of c.partidas; track $index) {
              <tr>
                <td class="py-1.5">{{ p.descripcion }}</td>
                <td class="py-1.5 text-right">{{ p.cantidad }} {{ unidad[p.unidad] }}</td>
                <td class="py-1.5 text-right">
                  {{ p.precio_unitario | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}
                </td>
                <td class="py-1.5 text-right font-semibold">
                  {{ p.importe | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      <dl class="mt-3 ml-auto grid max-w-xs grid-cols-2 gap-y-1 text-sm">
        <dt class="text-slate-500">Subtotal</dt>
        <dd class="text-right">{{ c.subtotal | currency: 'MXN' : 'symbol-narrow' : '1.2-2' }}</dd>
        <dt class="text-slate-500">IVA</dt>
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
      @if (c.notas) {
        <p class="mt-3 text-xs text-slate-600">{{ c.notas }}</p>
      }
      <p class="mt-2 text-[11px] text-slate-500">
        Versión {{ c.version }}
        @if (c.creada_por_nombre) {
          · {{ c.creada_por_nombre }}
        }
        @if (c.estado === 'vigente') {
          · vigente hasta {{ c.valida_hasta | date: 'dd/MM/yyyy HH:mm' }}
        }
      </p>
    }
  `,
})
export class CotizacionView {
  readonly cotizacion = input.required<Cotizacion>();
  protected readonly unidad = UNIDAD_LABEL;
}
