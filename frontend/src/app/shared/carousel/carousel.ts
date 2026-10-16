import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  effect,
  input,
  model,
  viewChild,
} from '@angular/core';
import { Icon } from '../icon/icon';

/**
 * Carrusel de fotos: se desliza con el dedo o el ratón (scroll con imanes), tiene flechas, puntos y
 * contador, y se maneja con el teclado (← →). `index` permite enlazarlo a una tira de miniaturas.
 */
@Component({
  selector: 'app-carousel',
  imports: [Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block' },
  template: `
    <div
      class="group relative overflow-hidden bg-slate-100 focus-visible:outline-2"
      [class]="rounded()"
      tabindex="0"
      role="group"
      aria-roledescription="carrusel"
      [attr.aria-label]="label()"
      (keydown.arrowleft)="go(index() - 1)"
      (keydown.arrowright)="go(index() + 1)"
    >
      <div
        #track
        class="flex snap-x snap-mandatory overflow-x-auto scroll-smooth [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        (scroll)="onScroll()"
      >
        @for (src of images(); track src; let i = $index) {
          <div class="w-full shrink-0 snap-center" [class]="aspect()">
            <img
              [src]="src"
              [alt]="label() + ' — foto ' + (i + 1)"
              class="size-full object-cover"
              [attr.loading]="i === 0 ? 'eager' : 'lazy'"
              draggable="false"
            />
          </div>
        } @empty {
          <div
            class="flex w-full items-center justify-center text-sm text-slate-400"
            [class]="aspect()"
          >
            Sin foto
          </div>
        }
      </div>

      @if (images().length > 1) {
        <button
          type="button"
          aria-label="Foto anterior"
          class="absolute top-1/2 left-3 grid size-9 -translate-y-1/2 place-items-center rounded-full bg-white/90 text-slate-700 shadow-md backdrop-blur transition hover:scale-105 hover:bg-white sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100"
          [class.invisible]="index() === 0"
          (click)="go(index() - 1)"
        >
          <app-icon name="flecha" class="size-4 rotate-180" />
        </button>
        <button
          type="button"
          aria-label="Foto siguiente"
          class="absolute top-1/2 right-3 grid size-9 -translate-y-1/2 place-items-center rounded-full bg-white/90 text-slate-700 shadow-md backdrop-blur transition hover:scale-105 hover:bg-white sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100"
          [class.invisible]="index() === images().length - 1"
          (click)="go(index() + 1)"
        >
          <app-icon name="flecha" class="size-4" />
        </button>

        <div class="absolute inset-x-0 bottom-3 flex justify-center gap-1.5">
          @for (src of images(); track src; let i = $index) {
            <button
              type="button"
              [attr.aria-label]="'Ir a la foto ' + (i + 1)"
              class="h-1.5 rounded-full transition-all"
              [class]="i === index() ? 'w-5 bg-white' : 'w-1.5 bg-white/60 hover:bg-white/90'"
              (click)="go(i)"
            ></button>
          }
        </div>
        <span
          class="absolute right-3 bottom-3 rounded-full bg-black/55 px-2 py-0.5 text-[11px] font-semibold text-white backdrop-blur"
          >{{ index() + 1 }} / {{ images().length }}</span
        >
      }
      <ng-content />
    </div>
  `,
})
export class Carousel {
  readonly images = input.required<string[]>();
  /** Descripción de las fotos (nombre del equipo). */
  readonly label = input('Fotos');
  /** Proporción de cada foto (clases de Tailwind). */
  readonly aspect = input('aspect-[16/10]');
  readonly rounded = input('rounded-2xl');
  /** Foto visible. Enlazable: `[(index)]`. */
  readonly index = model(0);

  private readonly track = viewChild.required<ElementRef<HTMLElement>>('track');
  /** Mientras el carrusel se desliza solo (flecha, punto, miniatura) no se escuchan sus pasos intermedios. */
  private settling = false;
  private settleTimer: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    // Cuando otro componente cambia `index` (p. ej. una miniatura), el carrusel se desliza ahí.
    effect(() => {
      const target = this.index();
      const el = this.track().nativeElement;
      if (el.clientWidth > 0 && Math.round(el.scrollLeft / el.clientWidth) !== target) {
        this.settling = true;
        clearTimeout(this.settleTimer);
        this.settleTimer = setTimeout(() => (this.settling = false), 700);
        el.scrollTo({ left: target * el.clientWidth });
      }
    });
  }

  protected go(i: number): void {
    const next = Math.max(0, Math.min(this.images().length - 1, i));
    this.index.set(next);
  }

  protected onScroll(): void {
    const el = this.track().nativeElement;
    if (this.settling || el.clientWidth === 0) return;
    const current = Math.round(el.scrollLeft / el.clientWidth);
    if (current !== this.index()) this.index.set(current);
  }
}
