import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { PlanMantenimiento } from '../../core/api/models';

const ESTILO: Record<PlanMantenimiento['estado'], { label: string; classes: string }> = {
  ok: { label: 'Al día', classes: 'bg-emerald-100 text-emerald-800' },
  proximo: { label: 'Próximo', classes: 'bg-amber-100 text-amber-800' },
  vencido: { label: 'Vencido', classes: 'bg-rose-100 text-rose-800' },
};

/** «faltan 40 h» o «se pasó por 10 h». */
function restante(valor: number, unidad: string): string {
  const cantidad = Math.abs(valor).toLocaleString('es-MX', { maximumFractionDigits: 1 });
  return valor <= 0 ? `se pasó por ${cantidad} ${unidad}` : `faltan ${cantidad} ${unidad}`;
}

/** Etiqueta del estado de un plan de mantenimiento y cuánto falta (o cuánto se pasó). */
@Component({
  selector: 'app-mantenimiento-estado',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="rounded-full px-2.5 py-0.5 text-[11px] font-bold" [class]="estilo().classes">{{
      estilo().label
    }}</span>
    <span class="ml-2 text-xs text-slate-500">{{ detalle() }}</span>
  `,
})
export class MantenimientoEstado {
  readonly plan =
    input.required<Pick<PlanMantenimiento, 'estado' | 'faltan_horas' | 'faltan_dias'>>();
  protected readonly estilo = computed(() => ESTILO[this.plan().estado]);
  protected readonly detalle = computed(() => {
    const { faltan_horas, faltan_dias } = this.plan();
    const partes: string[] = [];
    if (faltan_horas !== null) partes.push(restante(faltan_horas, 'h'));
    if (faltan_dias !== null) partes.push(restante(faltan_dias, 'días'));
    return partes.join(' · ');
  });
}
