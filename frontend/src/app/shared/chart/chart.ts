import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  effect,
  inject,
  input,
  viewChild,
} from '@angular/core';
import {
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  ChartConfiguration,
  DoughnutController,
  Filler,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from 'chart.js';

// Solo las piezas que se usan: el resto de Chart.js no entra al paquete.
Chart.register(
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  DoughnutController,
  Filler,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
);
Chart.defaults.font.family = "'Inter Variable', ui-sans-serif, system-ui, sans-serif";
Chart.defaults.color = '#64748b';

/** Gráfica de Chart.js: se redibuja sola cuando cambia `config`. Dale una altura al contenedor. */
@Component({
  selector: 'app-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'relative block h-full w-full' },
  template: `<canvas #canvas role="img" [attr.aria-label]="label()"></canvas>`,
})
export class ChartView {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  readonly config = input.required<ChartConfiguration<any, any, any>>();
  /** Descripción para lectores de pantalla. */
  readonly label = input('Gráfica');

  private readonly canvas = viewChild.required<ElementRef<HTMLCanvasElement>>('canvas');
  private chart: Chart | null = null;

  constructor() {
    afterNextRender(() => this.draw());
    effect(() => {
      this.config();
      if (this.chart) this.draw();
    });
    inject(DestroyRef).onDestroy(() => this.chart?.destroy());
  }

  private draw(): void {
    this.chart?.destroy();
    this.chart = new Chart(this.canvas().nativeElement, {
      ...this.config(),
      options: { responsive: true, maintainAspectRatio: false, ...this.config().options },
    });
  }
}
