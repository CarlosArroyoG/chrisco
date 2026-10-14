import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { EmpresaStatus } from '../../core/api/models';

const STYLES: Record<EmpresaStatus, { label: string; classes: string }> = {
  pendiente: { label: 'Pendiente de revisión', classes: 'bg-amber-100 text-amber-800' },
  aprobada: { label: 'Aprobada', classes: 'bg-emerald-100 text-emerald-800' },
  rechazada: { label: 'Rechazada', classes: 'bg-rose-100 text-rose-800' },
};

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
  readonly status = input.required<EmpresaStatus>();
  protected readonly style = computed(() => STYLES[this.status()]);
}
