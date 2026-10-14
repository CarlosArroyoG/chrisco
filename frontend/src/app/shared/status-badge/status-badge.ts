import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { EmpresaStatus, EquipoStatus } from '../../core/api/models';

type Status = EmpresaStatus | EquipoStatus;

const AMBER = 'bg-amber-100 text-amber-800';
const GREEN = 'bg-emerald-100 text-emerald-800';
const RED = 'bg-rose-100 text-rose-800';

const STYLES: Record<Status, { label: string; classes: string }> = {
  pendiente: { label: 'Pendiente de revisión', classes: AMBER },
  aprobada: { label: 'Aprobada', classes: GREEN },
  rechazada: { label: 'Rechazada', classes: RED },
  activo: { label: 'Activo', classes: GREEN },
  mantenimiento: { label: 'En mantenimiento', classes: AMBER },
  baja: { label: 'Baja', classes: 'bg-slate-200 text-slate-700' },
};

/** Etiqueta de color para el estado de una empresa o de un equipo. */
@Component({
  selector: 'app-status-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span
    class="rounded-full px-2.5 py-0.5 text-[11px] font-bold"
    [class]="style().classes"
  >
    {{ style().label }}
  </span>`,
})
export class StatusBadge {
  readonly status = input.required<Status>();
  protected readonly style = computed(() => STYLES[this.status()]);
}
