import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  input,
  output,
  signal,
} from '@angular/core';
import { Carousel } from '../carousel/carousel';
import { Icon } from '../icon/icon';

/** Una foto del equipo lista para mostrarse: ya subida o recién elegida y aún sin subir. */
export interface FotoItem {
  /** Identifica la foto al quitarla (su id, o la dirección temporal si aún no se sube). */
  key: string;
  /** Imagen grande para el carrusel. */
  url: string;
  /** Miniatura. */
  thumb: string;
}

/**
 * Fotos de un equipo como las verá el cliente: un carrusel con miniaturas, y para quien edita,
 * agregar y quitar. Sirve igual para un equipo que se está creando (fotos por subir) y para uno
 * ya guardado: quien lo usa decide qué hacer con `add` y `remove`.
 */
@Component({
  selector: 'app-fotos-equipo',
  imports: [Carousel, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card mt-4" aria-labelledby="fotos-titulo">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="fotos-titulo" class="text-sm font-black">
          Fotos ({{ fotos().length }}/{{ max() }})
        </h2>
        <p class="text-xs text-slate-500">La primera es la portada del catálogo.</p>
      </div>

      @if (fotos().length) {
        <div class="mt-4 grid gap-4 lg:grid-cols-[1.5fr_1fr]">
          <app-carousel
            [images]="urls()"
            label="Vista previa"
            aspect="aspect-[16/10]"
            [(index)]="index"
          />
          <ul class="grid grid-cols-3 content-start gap-2" aria-label="Miniaturas">
            @for (foto of fotos(); track foto.key; let i = $index) {
              <li class="relative">
                <button
                  type="button"
                  class="block w-full overflow-hidden rounded-xl border-2 transition"
                  [class]="
                    i === index()
                      ? 'border-chrisco-orange shadow-md'
                      : 'border-transparent opacity-75 hover:opacity-100'
                  "
                  [attr.aria-label]="'Ver foto ' + (i + 1)"
                  (click)="index.set(i)"
                >
                  <img
                    [src]="foto.thumb"
                    alt="Foto del equipo"
                    class="aspect-[4/3] w-full object-cover"
                  />
                </button>
                @if (i === 0) {
                  <span
                    class="bg-chrisco-orange pointer-events-none absolute bottom-1 left-1 rounded px-1.5 py-0.5 text-[10px] font-bold text-white"
                    >Portada</span
                  >
                }
                @if (canEdit()) {
                  <button
                    type="button"
                    (click)="remove.emit(foto.key)"
                    class="absolute top-1 right-1 grid size-6 place-items-center rounded-full bg-black/60 text-xs font-bold text-white transition hover:bg-rose-600"
                    aria-label="Quitar foto"
                  >
                    ✕
                  </button>
                }
              </li>
            }
          </ul>
        </div>
      } @else {
        <div
          class="mt-4 flex flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-slate-200 py-10 text-center"
        >
          <app-icon name="equipos" class="size-8 text-slate-300" />
          <p class="text-sm font-medium text-slate-500">Aún no hay fotos.</p>
        </div>
      }

      @if (canEdit() && fotos().length < max()) {
        <label
          for="fotos"
          class="hover:border-chrisco-orange mt-4 flex cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-300 px-4 py-4 text-sm font-semibold text-slate-600 transition hover:bg-orange-50/50"
        >
          <app-icon name="catalogo" class="size-5" />
          Agregar fotos (JPG, PNG o WebP)
          <input
            id="fotos"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            class="sr-only"
            (change)="onFiles($event)"
          />
        </label>
      }
      @if (error()) {
        <p role="alert" class="alert-error mt-3">{{ error() }}</p>
      }
    </section>
  `,
})
export class FotosEquipo {
  readonly fotos = input.required<FotoItem[]>();
  readonly canEdit = input(true);
  readonly max = input(10);
  readonly error = input<string | null>(null);

  /** El usuario eligió archivos. */
  readonly add = output<File[]>();
  /** El usuario quitó la foto con esa clave. */
  readonly remove = output<string>();

  protected readonly index = signal(0);
  protected readonly urls = computed(() => this.fotos().map((f) => f.url));

  constructor() {
    // Si se quita la última foto vista, el carrusel retrocede a una que exista.
    effect(() => {
      const last = this.fotos().length - 1;
      if (this.index() > last) this.index.set(Math.max(0, last));
    });
  }

  protected onFiles(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    input.value = '';
    if (files.length) this.add.emit(files);
  }
}
