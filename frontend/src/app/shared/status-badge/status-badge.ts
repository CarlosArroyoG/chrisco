import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { EmpresaStatus, EquipoStatus, EstadoActual, RentaEstado } from '../../core/api/models';

type Status = EmpresaStatus | EquipoStatus | EstadoActual | RentaEstado;

const AMBER = 'bg-amber-100 text-amber-800';
const GREEN = 'bg-emerald-100 text-emerald-800';
const RED = 'bg-rose-100 text-rose-800';
const SKY = 'bg-sky-100 text-sky-800';
const GRAY = 'bg-slate-200 text-slate-700';

const STYLES: Record<Status, { label: string; classes: string }> = {
  // Empresas
  pendiente: { label: 'Pendiente de revisión', classes: AMBER },
  aprobada: { label: 'Aprobada', classes: GREEN },
  rechazada: { label: 'Rechazada', classes: RED },
  // Equipos y su situación actual
  activo: { label: 'Activo', classes: GREEN },
  mantenimiento: { label: 'En mantenimiento', classes: AMBER },
  baja: { label: 'Baja', classes: GRAY },
  libre: { label: 'Libre', classes: GREEN },
  bloqueado: { label: 'Bloqueado', classes: AMBER },
  rentado: { label: 'Rentado', classes: SKY },
  // Rentas
  solicitada: { label: 'Solicitada', classes: AMBER },
  cotizada: { label: 'Cotizada', classes: SKY },
  apartada: { label: 'Apartada', classes: AMBER },
  confirmada: { label: 'Confirmada', classes: GREEN },
  en_renta: { label: 'En renta', classes: SKY },
  devuelta: { label: 'Devuelta', classes: GRAY },
  cerrada: { label: 'Cerrada', classes: GREEN },
  vencida: { label: 'Vencida', classes: GRAY },
  cancelada: { label: 'Cancelada', classes: GRAY },
};

/** Etiqueta de color para el estado de una empresa, un equipo o una renta. */
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
