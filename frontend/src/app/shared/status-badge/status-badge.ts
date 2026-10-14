import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { EmpresaStatus, EquipoStatus, EstadoActual } from '../../core/api/models';

type Status = EmpresaStatus | EquipoStatus | EstadoActual;

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
  libre: { label: 'Libre', classes: GREEN },
  bloqueado: { label: 'Bloqueado', classes: AMBER },
  rentado: { label: 'Rentado', classes: 'bg-sky-100 text-sky-800' },
};

/** Etiqueta de color para el estado de una empresa o la situación de un equipo. */
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
