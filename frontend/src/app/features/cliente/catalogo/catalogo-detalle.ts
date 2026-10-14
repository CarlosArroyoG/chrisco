import { CurrencyPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, input, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../../core/api/errors';
import { EquipoCatalogo } from '../../../core/api/models';
import { CatalogoService, fotoUrl } from '../../../core/catalogo/catalogo.service';

/** Ficha de un equipo del catálogo: fotos, especificaciones, tarifas y requisitos. */
@Component({
  selector: 'app-catalogo-detalle',
  imports: [CurrencyPipe, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a routerLink="/cliente/catalogo" class="link text-xs">← Volver al catálogo</a>
    @if (error()) {
      <p role="alert" class="alert-error mt-3">{{ error() }}</p>
    }
    @if (equipo(); as e) {
      <div class="mt-3 grid gap-4 lg:grid-cols-2">
        <section>
          @if (e.fotos.length) {
            <img
              [src]="fotoUrl(e.fotos[selected()].id, 'full')"
              [alt]="e.nombre"
              class="w-full rounded-2xl border object-cover"
            />
            @if (e.fotos.length > 1) {
              <div class="mt-2 flex gap-2 overflow-x-auto">
                @for (foto of e.fotos; track foto.id; let i = $index) {
                  <button
                    type="button"
                    (click)="selected.set(i)"
                    [attr.aria-label]="'Foto ' + (i + 1)"
                    class="shrink-0 overflow-hidden rounded-lg border-2"
                    [class]="i === selected() ? 'border-chrisco-orange' : 'border-transparent'"
                  >
                    <img [src]="fotoUrl(foto.id, 'thumb')" alt="" class="size-16 object-cover" />
                  </button>
                }
              </div>
            }
          } @else {
            <div
              class="flex aspect-[4/3] items-center justify-center rounded-2xl bg-slate-100 text-sm text-slate-400"
            >
              Sin foto
            </div>
          }
        </section>

        <section class="card space-y-3">
          <p class="text-[10px] font-bold text-slate-500 uppercase">{{ e.categoria_nombre }}</p>
          <h1 class="text-xl font-black">{{ e.nombre }}</h1>
          <p class="text-sm text-slate-600">
            {{ e.marca }} {{ e.modelo }}
            @if (e.anio) {
              · {{ e.anio }}
            }
            · {{ e.patio }}
          </p>

          <div class="rounded-xl bg-slate-50 p-3 text-sm">
            @if (e.tarifa_hora) {
              <p>
                <b>{{ e.tarifa_hora | currency: 'MXN' : 'symbol-narrow' : '1.0-2' }}</b> por hora
              </p>
            }
            @if (e.tarifa_dia) {
              <p>
                <b>{{ e.tarifa_dia | currency: 'MXN' : 'symbol-narrow' : '1.0-2' }}</b> por día
              </p>
            }
            <p class="mt-1 text-[11px] text-slate-500">
              Más IVA. El flete y otros cargos se cotizan aparte.
            </p>
          </div>

          <ul class="space-y-1 text-xs font-semibold">
            @if (e.requiere_lowboy) {
              <li class="text-amber-700">• Se transporta en lowboy</li>
            }
            @if (e.requiere_operador_certificado) {
              <li class="text-amber-700">• Requiere operador certificado</li>
            }
          </ul>

          @if (e.specs.length) {
            <dl class="grid grid-cols-2 gap-x-4 gap-y-2 border-t pt-3 text-sm">
              @for (s of e.specs; track s.label) {
                <dt class="text-slate-500">{{ s.label }}</dt>
                <dd class="font-semibold">{{ s.value }}{{ s.unit ? ' ' + s.unit : '' }}</dd>
              }
            </dl>
          }
        </section>
      </div>
    }
  `,
})
export class CatalogoDetalle implements OnInit {
  private readonly service = inject(CatalogoService);

  /** Id de la ruta `/cliente/catalogo/:id`. */
  readonly id = input.required<string>();

  protected readonly fotoUrl = fotoUrl;
  protected readonly equipo = signal<EquipoCatalogo | null>(null);
  protected readonly selected = signal(0);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.service.get(this.id()).subscribe({
      next: (equipo) => this.equipo.set(equipo),
      error: (err: unknown) => this.error.set(apiErrorMessage(err, 'No se pudo cargar el equipo.')),
    });
  }
}
