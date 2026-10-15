import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../../core/api/errors';
import { MantenimientoAtencion } from '../../../core/api/models';
import { MantenimientoEstado } from '../../../shared/mantenimiento-estado/mantenimiento-estado';
import { MantenimientoService } from './mantenimiento.service';

/** Mantenimiento de toda la flotilla: lo vencido y lo próximo primero. */
@Component({
  selector: 'app-mantenimiento-page',
  imports: [DecimalPipe, ReactiveFormsModule, RouterLink, MantenimientoEstado],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1 class="text-lg font-black">Mantenimiento</h1>
    <p class="text-xs text-slate-500">
      Los administradores reciben un correo cuando un servicio se acerca y cuando vence. Los planes
      se dan de alta en la ficha de cada equipo.
    </p>

    <label class="mt-3 flex items-center gap-2 text-xs">
      <input type="checkbox" [formControl]="soloAtencion" />
      Solo lo que requiere atención
    </label>

    @if (error()) {
      <p role="alert" class="alert-error mt-3">{{ error() }}</p>
    }

    <div class="mt-3 overflow-x-auto rounded-xl border bg-white">
      <table class="w-full text-left text-xs">
        <thead class="bg-chrisco-charcoal text-[10px] font-bold text-white uppercase">
          <tr>
            <th class="p-3">Equipo</th>
            <th class="p-3">Servicio</th>
            <th class="p-3 text-right">Horómetro</th>
            <th class="p-3">Estado</th>
            <th class="p-3"></th>
          </tr>
        </thead>
        <tbody class="divide-y">
          @for (i of items(); track i.id) {
            <tr [attr.data-plan]="i.nombre">
              <td class="p-3">
                <span class="font-semibold">{{ i.equipo_nombre }}</span
                ><br /><span class="text-slate-500">{{ i.equipo_codigo }}</span>
              </td>
              <td class="p-3">{{ i.nombre }}</td>
              <td class="p-3 text-right">{{ i.horometro_actual | number: '1.0-1' }} h</td>
              <td class="p-3"><app-mantenimiento-estado [plan]="i" /></td>
              <td class="p-3">
                <a [routerLink]="['/admin/equipos', i.equipo_id]" class="link">Ver equipo</a>
              </td>
            </tr>
          } @empty {
            <tr>
              <td colspan="5" class="p-6 text-center text-slate-500">
                {{ loaded() ? 'No hay mantenimientos pendientes.' : 'Cargando…' }}
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  `,
})
export class MantenimientoPage implements OnInit {
  private readonly service = inject(MantenimientoService);

  protected readonly soloAtencion = new FormControl(false, { nonNullable: true });
  protected readonly items = signal<MantenimientoAtencion[]>([]);
  protected readonly loaded = signal(false);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.soloAtencion.valueChanges.subscribe(() => this.load());
    this.load();
  }

  private load(): void {
    this.loaded.set(false);
    this.error.set(null);
    this.service.atencion(this.soloAtencion.value).subscribe({
      next: (items) => {
        this.items.set(items);
        this.loaded.set(true);
      },
      error: (err: unknown) => {
        this.loaded.set(true);
        this.error.set(apiErrorMessage(err, 'No se pudo cargar el mantenimiento.'));
      },
    });
  }
}
