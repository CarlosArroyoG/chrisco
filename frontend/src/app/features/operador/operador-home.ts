import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { apiErrorMessage } from '../../core/api/errors';
import { Renta } from '../../core/api/models';
import { RentasService } from '../../core/rentas/rentas.service';

/** Inicio del operador: los equipos por entregar y los que están en obra por recibir. */
@Component({
  selector: 'app-operador-home',
  imports: [DatePipe, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1 class="page-title">Entregas y devoluciones</h1>
    @if (error()) {
      <p role="alert" class="alert-error mt-3">{{ error() }}</p>
    }

    <section class="mt-4" aria-labelledby="por-entregar">
      <h2 id="por-entregar" class="text-sm font-black">
        Por entregar ({{ porEntregar().length }})
      </h2>
      <ul class="mt-2 space-y-2" aria-label="Por entregar">
        @for (r of porEntregar(); track r.id) {
          <li class="card flex flex-wrap items-center justify-between gap-2">
            <div class="text-sm">
              <p class="font-semibold">{{ r.equipo_nombre }} ({{ r.equipo_codigo }})</p>
              <p class="text-xs text-slate-500">
                {{ r.empresa_razon_social }} · {{ r.destino }} · {{ r.desde | date: 'dd/MM HH:mm' }}
              </p>
            </div>
            <a [routerLink]="['/operador', r.id]" class="btn-primary">Entregar</a>
          </li>
        } @empty {
          <li class="text-xs text-slate-500">
            {{ loaded() ? 'No hay equipos por entregar.' : 'Cargando…' }}
          </li>
        }
      </ul>
    </section>

    <section class="mt-6" aria-labelledby="en-obra">
      <h2 id="en-obra" class="text-sm font-black">En obra, por recibir ({{ enObra().length }})</h2>
      <ul class="mt-2 space-y-2" aria-label="En obra">
        @for (r of enObra(); track r.id) {
          <li class="card flex flex-wrap items-center justify-between gap-2">
            <div class="text-sm">
              <p class="font-semibold">{{ r.equipo_nombre }} ({{ r.equipo_codigo }})</p>
              <p class="text-xs text-slate-500">
                {{ r.empresa_razon_social }} · {{ r.destino }} · regresa
                {{ r.hasta | date: 'dd/MM HH:mm' }}
              </p>
            </div>
            <a [routerLink]="['/operador', r.id]" class="btn-secondary">Recibir</a>
          </li>
        } @empty {
          <li class="text-xs text-slate-500">
            {{ loaded() ? 'No hay equipos en obra.' : 'Cargando…' }}
          </li>
        }
      </ul>
    </section>
  `,
})
export class OperadorHome implements OnInit {
  private readonly service = inject(RentasService);

  protected readonly porEntregar = signal<Renta[]>([]);
  protected readonly enObra = signal<Renta[]>([]);
  protected readonly loaded = signal(false);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    forkJoin([
      this.service.list({ estado: 'confirmada', limit: 100 }),
      this.service.list({ estado: 'en_renta', limit: 100 }),
    ]).subscribe({
      next: ([confirmadas, enRenta]) => {
        this.porEntregar.set(confirmadas.items);
        this.enObra.set(enRenta.items);
        this.loaded.set(true);
      },
      error: (err: unknown) => {
        this.loaded.set(true);
        this.error.set(apiErrorMessage(err, 'No se pudieron cargar las entregas.'));
      },
    });
  }
}
