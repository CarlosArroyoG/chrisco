import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { EmpresaStatus, EquipoStatus, EstadoActual, RentaEstado } from '../../core/api/models';

type Status = EmpresaStatus | EquipoStatus | EstadoActual | RentaEstado;

const AMBER = 'bg-amber-50 text-amber-700';
const GREEN = 'bg-emerald-50 text-emerald-700';
const RED = 'bg-rose-50 text-rose-700';
const SKY = 'bg-sky-50 text-sky-700';
const GRAY = 'bg-slate-100 text-slate-600';

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
    class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ring-black/5"
    [class]="style().classes"
  >
    <span class="size-1.5 rounded-full bg-current opacity-70"></span>
    {{ style().label }}
  </span>`,
})
export class StatusBadge {
  readonly status = input.required<Status>();
  protected readonly style = computed(() => STYLES[this.status()]);
}
