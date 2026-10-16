import { CurrencyPipe, DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { ChartConfiguration } from 'chart.js';
import { apiErrorMessage } from '../../../core/api/errors';
import { Dashboard, RentaEstado } from '../../../core/api/models';
import { AuthService } from '../../../core/auth/auth.service';
import { ChartView } from '../../../shared/chart/chart';
import { Icon, IconName } from '../../../shared/icon/icon';
import { KpiCard } from '../../../shared/kpi-card/kpi-card';
import { DashboardService } from './dashboard.service';

const ESTADO_LABEL: Record<RentaEstado, string> = {
  solicitada: 'Solicitadas',
  cotizada: 'Cotizadas',
  apartada: 'Apartadas',
  confirmada: 'Confirmadas',
  en_renta: 'En renta',
  devuelta: 'Devueltas',
  cerrada: 'Cerradas',
  vencida: 'Vencidas',
  cancelada: 'Canceladas',
  rechazada: 'Rechazadas',
};

const CATEGORIA_LABEL: Record<string, string> = {
  mantenimiento: 'Mantenimiento',
  refacciones: 'Refacciones',
  combustible: 'Combustible',
  operador: 'Operador',
  flete: 'Flete',
  otro: 'Otros',
};

const PALETA = ['#f58220', '#0ea5e9', '#10b981', '#8b5cf6', '#f43f5e', '#94a3b8', '#eab308'];

const ACCESOS: { path: string; titulo: string; texto: string; icon: IconName }[] = [
  {
    path: '/admin/rentas',
    titulo: 'Rentas',
    texto: 'Solicitudes, cotizaciones y entregas',
    icon: 'rentas',
  },
  {
    path: '/admin/cobranza',
    titulo: 'Cobranza',
    texto: 'Lo cobrado y lo que falta',
    icon: 'cobranza',
  },
  { path: '/admin/equipos', titulo: 'Equipos', texto: 'Flota, fotos y tarifas', icon: 'equipos' },
  {
    path: '/admin/mantenimiento',
    titulo: 'Mantenimiento',
    texto: 'Servicios y alertas',
    icon: 'mantenimiento',
  },
  {
    path: '/admin/empresas',
    titulo: 'Empresas',
    texto: 'Revisar y aprobar clientes',
    icon: 'empresas',
  },
  {
    path: '/admin/gastos',
    titulo: 'Gastos',
    texto: 'Combustible, refacciones y más',
    icon: 'gastos',
  },
];

/** Panel del administrador: cifras del mes, gráficas y lo que requiere atención. */
@Component({
  selector: 'app-dashboard-page',
  imports: [CurrencyPipe, DatePipe, DecimalPipe, RouterLink, ChartView, Icon, KpiCard],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p class="eyebrow">Resumen de {{ data()?.mes_nombre ?? 'este mes' }}</p>
        <h1 class="page-title">Hola, {{ firstName() }}</h1>
      </div>
      <a routerLink="/admin/gastos" class="btn-secondary">
        <app-icon name="gastos" class="size-4" /> Registrar un gasto
      </a>
    </div>

    @if (error()) {
      <p role="alert" class="alert-error mt-4">{{ error() }}</p>
    }

    @if (data(); as d) {
      <!-- Ganancia del mes + indicadores principales -->
      <section class="mt-6 grid gap-4 lg:grid-cols-3" aria-label="Resultados del mes">
        <div
          class="relative overflow-hidden rounded-2xl p-6 text-white shadow-lg lg:row-span-1"
          [class]="
            d.ganancia.actual >= 0
              ? 'bg-linear-to-br from-emerald-500 to-teal-600 shadow-emerald-600/20'
              : 'bg-linear-to-br from-rose-500 to-red-600 shadow-rose-600/20'
          "
        >
          <div
            class="pointer-events-none absolute -right-8 -bottom-12 size-48 rounded-full bg-white/10"
          ></div>
          <div
            class="pointer-events-none absolute -top-10 -left-6 size-32 rounded-full bg-white/10"
          ></div>
          <p class="relative text-sm font-medium text-white/80">
            {{ d.ganancia.actual >= 0 ? 'Ganancia del mes' : 'Pérdida del mes' }}
          </p>
          <p class="relative mt-2 text-4xl font-extrabold tracking-tight" data-testid="ganancia">
            {{ d.ganancia.actual | currency: 'MXN' : 'symbol-narrow' : '1.0-0' }}
          </p>
          <p class="relative mt-1 text-xs text-white/80">
            Cobrado menos gastos de {{ d.mes_nombre }}
          </p>
          <div class="relative mt-4 h-16">
            <app-chart [config]="sparkline()" label="Tendencia de la ganancia" />
          </div>
          <p class="relative mt-3 text-xs text-white/90">
            @if (d.ganancia.cambio_pct === null) {
              Sin mes anterior para comparar
            } @else {
              {{ (d.ganancia.cambio_pct ?? 0) >= 0 ? '▲' : '▼' }}
              {{ abs(d.ganancia.cambio_pct) | number: '1.0-0' }}% vs. mes anterior
            }
          </p>
        </div>

        <div class="grid gap-4 sm:grid-cols-2 lg:col-span-2">
          <app-kpi-card
            label="Ingresos cobrados"
            icon="cobranza"
            tone="orange"
            [value]="d.ingresos.actual"
            [change]="d.ingresos.cambio_pct"
            link="/admin/cobranza"
          />
          <app-kpi-card
            label="Gastos del mes"
            icon="gastos"
            tone="rose"
            [value]="d.gastos.actual"
            [change]="d.gastos.cambio_pct"
            [inverse]="true"
            link="/admin/gastos"
          />
          <app-kpi-card
            label="Vendido (cotizaciones aceptadas)"
            icon="tendencia"
            tone="violet"
            [value]="d.vendido.actual"
            [change]="d.vendido.cambio_pct"
          />
          <app-kpi-card
            label="Por cobrar"
            icon="reloj"
            tone="amber"
            [value]="d.por_cobrar"
            hint="Saldo de rentas con cotización aceptada"
            link="/admin/cobranza"
          />
        </div>
      </section>

      <!-- Operación del día -->
      <section class="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Operación">
        <div class="card hover:shadow-lift transition duration-200 hover:-translate-y-0.5">
          <div class="flex items-start justify-between">
            <p class="text-sm font-medium text-slate-500">Flota en renta</p>
            <span class="grid size-10 place-items-center rounded-xl bg-sky-100 text-sky-600">
              <app-icon name="equipos" class="size-5" />
            </span>
          </div>
          <p class="mt-3 text-3xl font-extrabold tracking-tight">
            {{ d.flota.rentados
            }}<span class="text-lg font-semibold text-slate-400"> / {{ d.flota.total }}</span>
          </p>
          <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              class="from-chrisco-orange h-full rounded-full bg-linear-to-r to-amber-400 transition-all duration-700"
              [style.width.%]="d.flota.utilizacion_pct"
            ></div>
          </div>
          <p class="mt-2 text-xs text-slate-500">
            {{ d.flota.utilizacion_pct | number: '1.0-0' }}% de utilización ·
            {{ d.flota.libres }} libres · {{ d.flota.bloqueados }} apartados
          </p>
        </div>

        <app-kpi-card
          label="Pagos por confirmar"
          icon="check"
          tone="emerald"
          [money]="false"
          [value]="d.pagos_por_confirmar"
          [hint]="d.pagos_por_confirmar ? 'Revisa los comprobantes' : 'Todo al día'"
          link="/admin/rentas"
        />
        <app-kpi-card
          label="Empresas por revisar"
          icon="empresas"
          tone="sky"
          [money]="false"
          [value]="d.empresas_pendientes"
          [hint]="d.empresas_pendientes ? 'Esperan tu aprobación' : 'Sin pendientes'"
          link="/admin/empresas"
        />
        <app-kpi-card
          label="Mantenimientos vencidos"
          icon="alerta"
          [tone]="d.mantenimiento.vencidos ? 'rose' : 'slate'"
          [money]="false"
          [value]="d.mantenimiento.vencidos"
          [hint]="d.mantenimiento.proximos + ' por vencer pronto'"
          link="/admin/mantenimiento"
        />
      </section>

      <!-- Gráficas -->
      <section class="mt-4 grid gap-4 lg:grid-cols-3" aria-label="Gráficas">
        <div class="card lg:col-span-2">
          <div class="flex items-center justify-between">
            <div>
              <h2 class="font-bold text-slate-900">Ingresos y gastos</h2>
              <p class="text-xs text-slate-500">Últimos 6 meses, con la ganancia de cada uno</p>
            </div>
          </div>
          <div class="mt-4 h-72">
            <app-chart [config]="barras()" label="Ingresos, gastos y ganancia por mes" />
          </div>
        </div>
        <div class="card">
          <h2 class="font-bold text-slate-900">Gastos por categoría</h2>
          <p class="text-xs text-slate-500">{{ d.mes_nombre }}</p>
          @if (d.gastos_por_categoria.length) {
            <div class="mt-4 h-60">
              <app-chart [config]="donaGastos()" label="Gastos por categoría" />
            </div>
          } @else {
            <p class="mt-10 text-center text-sm text-slate-400">Aún no hay gastos este mes.</p>
          }
        </div>
      </section>

      <section class="mt-4 grid gap-4 lg:grid-cols-3" aria-label="Detalle">
        <div class="card">
          <h2 class="font-bold text-slate-900">Rentas por estado</h2>
          @if (d.rentas_por_estado.length) {
            <div class="mt-4 h-60">
              <app-chart [config]="rentasEstado()" label="Rentas por estado" />
            </div>
          } @else {
            <p class="mt-10 text-center text-sm text-slate-400">Aún no hay rentas.</p>
          }
        </div>

        <div class="card">
          <h2 class="font-bold text-slate-900">Equipos que más ingresan</h2>
          <p class="text-xs text-slate-500">Cobrado en {{ d.mes_nombre }}</p>
          <ul class="mt-4 space-y-4" aria-label="Equipos con más ingresos">
            @for (e of d.top_equipos; track e.equipo_id) {
              <li>
                <div class="flex items-center justify-between text-sm">
                  <span class="truncate font-semibold">{{ e.nombre }}</span>
                  <span class="font-bold">{{
                    e.ingresos | currency: 'MXN' : 'symbol-narrow' : '1.0-0'
                  }}</span>
                </div>
                <div class="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    class="from-chrisco-orange h-full rounded-full bg-linear-to-r to-amber-400"
                    [style.width.%]="share(e.ingresos)"
                  ></div>
                </div>
              </li>
            } @empty {
              <li class="py-6 text-center text-sm text-slate-400">Sin cobros este mes.</li>
            }
          </ul>
        </div>

        <div class="card">
          <h2 class="font-bold text-slate-900">Próximas salidas</h2>
          <p class="text-xs text-slate-500">Rentas confirmadas por entregar</p>
          <ul class="mt-4 space-y-3" aria-label="Próximas salidas">
            @for (s of d.proximas_salidas; track s.renta_id) {
              <li>
                <a
                  [routerLink]="['/admin/rentas', s.renta_id]"
                  class="group flex items-center gap-3 rounded-xl border border-slate-100 p-3 transition hover:border-orange-200 hover:bg-orange-50/50"
                >
                  <span
                    class="grid size-10 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-600"
                  >
                    <app-icon name="entregas" class="size-5" />
                  </span>
                  <div class="min-w-0 flex-1">
                    <p class="truncate text-sm font-semibold">{{ s.equipo }}</p>
                    <p class="truncate text-xs text-slate-500">{{ s.empresa }}</p>
                  </div>
                  <span class="text-xs font-semibold text-slate-500">{{
                    s.desde | date: 'dd MMM'
                  }}</span>
                </a>
              </li>
            } @empty {
              <li class="py-6 text-center text-sm text-slate-400">No hay entregas pendientes.</li>
            }
          </ul>
        </div>
      </section>

      <!-- Accesos rápidos -->
      <section class="mt-8" aria-label="Accesos rápidos">
        <h2 class="eyebrow mb-3">Accesos rápidos</h2>
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          @for (a of accesos; track a.path) {
            <a
              [routerLink]="a.path"
              class="card group hover:shadow-lift flex items-center gap-4 transition duration-200 hover:-translate-y-0.5 hover:border-orange-200"
            >
              <span
                class="group-hover:bg-chrisco-orange grid size-12 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-600 transition group-hover:text-white"
              >
                <app-icon [name]="a.icon" class="size-6" />
              </span>
              <div class="min-w-0 flex-1">
                <p class="font-bold text-slate-900">{{ a.titulo }}</p>
                <p class="truncate text-xs text-slate-500">{{ a.texto }}</p>
              </div>
              <app-icon
                name="flecha"
                class="size-5 text-slate-300 transition group-hover:translate-x-1 group-hover:text-orange-500"
              />
            </a>
          }
        </div>
      </section>
    } @else if (!error()) {
      <div class="mt-6 grid gap-4 lg:grid-cols-3" aria-busy="true">
        @for (i of [1, 2, 3]; track i) {
          <div class="card h-40 animate-pulse bg-slate-100/70"></div>
        }
      </div>
    }
  `,
})
export class DashboardPage implements OnInit {
  private readonly service = inject(DashboardService);
  private readonly auth = inject(AuthService);

  protected readonly accesos = ACCESOS;
  protected readonly data = signal<Dashboard | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly firstName = computed(() => this.auth.user()?.full_name.split(' ')[0] ?? '');

  /** Lo cobrado por el equipo que más ingresó: las demás barras se miden contra él. */
  private readonly maxTop = computed(() =>
    Math.max(1, ...(this.data()?.top_equipos ?? []).map((e) => e.ingresos)),
  );

  protected readonly sparkline = computed<ChartConfiguration<'line'>>(() => {
    const serie = this.data()?.serie_mensual ?? [];
    return {
      type: 'line',
      data: {
        labels: serie.map((p) => p.etiqueta),
        datasets: [
          {
            data: serie.map((p) => p.ganancia),
            borderColor: 'rgba(255,255,255,0.95)',
            backgroundColor: 'rgba(255,255,255,0.18)',
            fill: true,
            tension: 0.4,
            pointRadius: 0,
            borderWidth: 2.5,
          },
        ],
      },
      options: {
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: { x: { display: false }, y: { display: false } },
      },
    };
  });

  protected readonly barras = computed<ChartConfiguration<'bar' | 'line'>>(() => {
    const serie = this.data()?.serie_mensual ?? [];
    return {
      type: 'bar',
      data: {
        labels: serie.map((p) => p.etiqueta),
        datasets: [
          {
            type: 'bar',
            label: 'Ingresos',
            data: serie.map((p) => p.ingresos),
            backgroundColor: '#f58220',
            borderRadius: 8,
            maxBarThickness: 36,
          },
          {
            type: 'bar',
            label: 'Gastos',
            data: serie.map((p) => p.gastos),
            backgroundColor: '#cbd5e1',
            borderRadius: 8,
            maxBarThickness: 36,
          },
          {
            type: 'line',
            label: 'Ganancia',
            data: serie.map((p) => p.ganancia),
            borderColor: '#10b981',
            backgroundColor: '#10b981',
            tension: 0.35,
            borderWidth: 3,
            pointRadius: 4,
            pointBackgroundColor: '#fff',
            pointBorderWidth: 2,
          },
        ],
      },
      options: {
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8 } },
          tooltip: {
            backgroundColor: '#1a2227',
            padding: 12,
            cornerRadius: 10,
            callbacks: {
              label: (ctx) =>
                `${ctx.dataset.label}: ${Number(ctx.parsed.y).toLocaleString('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 })}`,
            },
          },
        },
        scales: {
          x: { grid: { display: false }, border: { display: false } },
          y: {
            border: { display: false },
            grid: { color: '#eef0f3' },
            ticks: { callback: (v) => `$${Number(v).toLocaleString('es-MX')}` },
          },
        },
      },
    };
  });

  protected readonly donaGastos = computed<ChartConfiguration<'doughnut'>>(() => {
    const items = this.data()?.gastos_por_categoria ?? [];
    return {
      type: 'doughnut',
      data: {
        labels: items.map((i) => CATEGORIA_LABEL[i.categoria] ?? i.categoria),
        datasets: [
          {
            data: items.map((i) => i.total),
            backgroundColor: PALETA,
            borderWidth: 3,
            borderColor: '#fff',
            hoverOffset: 8,
          },
        ],
      },
      options: {
        cutout: '68%',
        plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8 } } },
      },
    };
  });

  protected readonly rentasEstado = computed<ChartConfiguration<'doughnut'>>(() => {
    const items = this.data()?.rentas_por_estado ?? [];
    return {
      type: 'doughnut',
      data: {
        labels: items.map((i) => ESTADO_LABEL[i.estado]),
        datasets: [
          {
            data: items.map((i) => i.total),
            backgroundColor: PALETA,
            borderWidth: 3,
            borderColor: '#fff',
            hoverOffset: 8,
          },
        ],
      },
      options: {
        cutout: '68%',
        plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8 } } },
      },
    };
  });

  ngOnInit(): void {
    this.service.get().subscribe({
      next: (data) => this.data.set(data),
      error: (err: unknown) => this.error.set(apiErrorMessage(err, 'No se pudo cargar el panel.')),
    });
  }

  protected abs(value: number | null): number {
    return Math.abs(value ?? 0);
  }

  protected share(ingresos: number): number {
    return Math.max(4, (ingresos / this.maxTop()) * 100);
  }
}
