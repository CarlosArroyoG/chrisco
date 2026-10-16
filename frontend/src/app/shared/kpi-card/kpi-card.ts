import { CurrencyPipe, DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Icon, IconName } from '../icon/icon';

export type KpiTone = 'orange' | 'emerald' | 'rose' | 'sky' | 'violet' | 'amber' | 'slate';

const TONES: Record<KpiTone, { icon: string; glow: string }> = {
  orange: { icon: 'bg-orange-100 text-orange-600', glow: 'group-hover:bg-orange-400/10' },
  emerald: { icon: 'bg-emerald-100 text-emerald-600', glow: 'group-hover:bg-emerald-400/10' },
  rose: { icon: 'bg-rose-100 text-rose-600', glow: 'group-hover:bg-rose-400/10' },
  sky: { icon: 'bg-sky-100 text-sky-600', glow: 'group-hover:bg-sky-400/10' },
  violet: { icon: 'bg-violet-100 text-violet-600', glow: 'group-hover:bg-violet-400/10' },
  amber: { icon: 'bg-amber-100 text-amber-600', glow: 'group-hover:bg-amber-400/10' },
  slate: { icon: 'bg-slate-100 text-slate-600', glow: 'group-hover:bg-slate-400/10' },
};

/**
 * Tarjeta de un indicador: ícono, cifra grande y, si se indica, cuánto cambió contra el mes
 * anterior. Con `link` toda la tarjeta lleva a otra pantalla y reacciona al pasar el cursor.
 */
@Component({
  selector: 'app-kpi-card',
  imports: [CurrencyPipe, DecimalPipe, NgTemplateOutlet, RouterLink, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (link(); as to) {
      <a
        [routerLink]="to"
        class="card group hover:shadow-lift relative block h-full overflow-hidden transition duration-200 hover:-translate-y-0.5"
      >
        <ng-container *ngTemplateOutlet="body" />
      </a>
    } @else {
      <div class="card group relative h-full overflow-hidden">
        <ng-container *ngTemplateOutlet="body" />
      </div>
    }

    <ng-template #body>
      <div
        class="pointer-events-none absolute -top-10 -right-10 size-32 rounded-full bg-transparent blur-2xl transition duration-300"
        [class]="palette().glow"
      ></div>
      <div class="relative flex items-start justify-between gap-3">
        <p class="text-sm font-medium text-slate-500">{{ label() }}</p>
        <span class="grid size-10 place-items-center rounded-xl" [class]="palette().icon">
          <app-icon [name]="icon()" class="size-5" />
        </span>
      </div>
      <p class="relative mt-3 text-3xl font-extrabold tracking-tight text-slate-900">
        @if (money()) {
          {{ value() | currency: 'MXN' : 'symbol-narrow' : '1.0-0' }}
        } @else {
          {{ value() | number: '1.0-0' }}{{ suffix() }}
        }
      </p>
      <div class="relative mt-2 flex flex-wrap items-center gap-2 text-xs">
        @if (change() !== undefined) {
          @if (change() === null) {
            <span class="text-slate-400">Sin mes anterior para comparar</span>
          } @else {
            <span
              class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-semibold"
              [class]="good() ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'"
            >
              {{ (change() ?? 0) >= 0 ? '▲' : '▼' }} {{ abs() | number: '1.0-0' }}%
            </span>
            <span class="text-slate-400">vs. mes anterior</span>
          }
        }
        @if (hint()) {
          <span class="text-slate-500">{{ hint() }}</span>
        }
      </div>
    </ng-template>
  `,
})
export class KpiCard {
  readonly label = input.required<string>();
  readonly value = input.required<number>();
  readonly icon = input.required<IconName>();
  readonly tone = input<KpiTone>('slate');
  protected readonly palette = computed(() => TONES[this.tone()]);
  readonly money = input(true);
  readonly suffix = input('');
  /** Variación en %: `undefined` oculta el comparativo; `null` avisa que no hay mes anterior. */
  readonly change = input<number | null | undefined>(undefined);
  /** Si más es peor (gastos), una subida se pinta en rojo. */
  readonly inverse = input(false);
  readonly hint = input('');
  readonly link = input<string | null>(null);

  protected readonly abs = computed(() => Math.abs(this.change() ?? 0));
  protected readonly good = computed(() => (this.change() ?? 0) >= 0 !== this.inverse());
}
