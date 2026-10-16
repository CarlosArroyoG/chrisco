import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RentaEstado } from '../../core/api/models';
import { Icon } from '../icon/icon';

const PASOS: { etiqueta: string; estados: RentaEstado[] }[] = [
  { etiqueta: 'Solicitud', estados: ['solicitada'] },
  { etiqueta: 'Cotización', estados: ['cotizada'] },
  { etiqueta: 'Apartado', estados: ['apartada'] },
  { etiqueta: 'Confirmada', estados: ['confirmada'] },
  { etiqueta: 'En renta', estados: ['en_renta'] },
  { etiqueta: 'Cerrada', estados: ['devuelta', 'cerrada'] },
];

/** Línea de avance de una renta: qué pasos ya se cumplieron, cuál es el actual y cuáles faltan. */
@Component({
  selector: 'app-renta-pasos',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (actual() >= 0) {
      <ol class="flex items-center" [attr.aria-label]="'Etapa: ' + pasos[actual()].etiqueta">
        @for (p of pasos; track p.etiqueta; let i = $index) {
          <li class="flex items-center" [class.flex-1]="i < pasos.length - 1">
            <span
              class="grid size-6 shrink-0 place-items-center rounded-full text-[10px] font-bold transition"
              [class]="
                i < actual()
                  ? 'bg-emerald-500 text-white'
                  : i === actual()
                    ? 'bg-chrisco-orange ring-4 ring-orange-100 text-white'
                    : 'bg-slate-100 text-slate-400'
              "
              [attr.title]="p.etiqueta"
            >
              @if (i < actual()) {
                <app-icon name="check" class="size-3.5" />
              } @else {
                {{ i + 1 }}
              }
            </span>
            @if (i < pasos.length - 1) {
              <span
                class="mx-1 h-0.5 flex-1 rounded-full"
                [class]="i < actual() ? 'bg-emerald-400' : 'bg-slate-200'"
              ></span>
            }
          </li>
        }
      </ol>
      @if (etiquetas()) {
        <p class="mt-1.5 text-[11px] font-semibold text-slate-500">
          Paso {{ actual() + 1 }} de {{ pasos.length }} · {{ pasos[actual()].etiqueta }}
        </p>
      }
    }
  `,
})
export class RentaPasos {
  readonly estado = input.required<RentaEstado>();
  /** Muestra «Paso 3 de 6 · Apartado» debajo de la línea. */
  readonly etiquetas = input(true);

  protected readonly pasos = PASOS;
  /** Índice del paso actual; -1 para las rentas que no siguieron (vencida, cancelada, rechazada). */
  protected readonly actual = computed(() =>
    PASOS.findIndex((p) => p.estados.includes(this.estado())),
  );
}
