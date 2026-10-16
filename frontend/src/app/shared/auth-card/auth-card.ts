import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { Icon, IconName } from '../icon/icon';
import { Logo } from '../logo/logo';

const BENEFICIOS: { icon: IconName; titulo: string; texto: string }[] = [
  {
    icon: 'catalogo',
    titulo: 'Catálogo en línea',
    texto: 'Mira la maquinaria disponible para tus fechas.',
  },
  {
    icon: 'reloj',
    titulo: 'Reserva al instante',
    texto: 'Tu equipo queda apartado mientras cotizamos.',
  },
  { icon: 'escudo', titulo: 'Todo en regla', texto: 'Contrato, póliza y pagos en un solo lugar.' },
];

/** Pantalla dividida de las pantallas públicas (login, registro…): marca a la izquierda, formulario a la derecha. */
@Component({
  selector: 'app-auth-card',
  imports: [Logo, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="fixed inset-0 overflow-y-auto bg-white lg:grid lg:grid-cols-[1.05fr_1fr]">
      <aside
        class="bg-chrisco-dark relative hidden flex-col justify-between overflow-hidden p-12 text-white lg:flex"
      >
        <div
          class="bg-chrisco-orange/30 pointer-events-none absolute -top-32 -right-24 size-96 rounded-full blur-3xl"
        ></div>
        <div
          class="pointer-events-none absolute -bottom-40 -left-24 size-[28rem] rounded-full bg-sky-500/10 blur-3xl"
        ></div>
        <div
          class="pointer-events-none absolute inset-0 opacity-[0.07] [background-image:repeating-linear-gradient(135deg,#fff_0_2px,transparent_2px_26px)]"
        ></div>

        <app-logo [onDark]="true" class="relative h-16 self-start" />

        <div class="relative max-w-md">
          <p class="text-chrisco-orange text-sm font-bold tracking-wider uppercase">
            Renta de maquinaria pesada
          </p>
          <h2 class="mt-3 text-4xl leading-tight font-extrabold tracking-tight">
            La maquinaria que tu obra necesita, en minutos.
          </h2>
          <ul class="mt-10 space-y-5">
            @for (b of beneficios; track b.titulo) {
              <li class="flex gap-4">
                <span
                  class="grid size-10 shrink-0 place-items-center rounded-xl bg-white/10 text-orange-300 ring-1 ring-white/10"
                >
                  <app-icon [name]="b.icon" class="size-5" />
                </span>
                <div>
                  <p class="font-semibold">{{ b.titulo }}</p>
                  <p class="text-sm text-slate-400">{{ b.texto }}</p>
                </div>
              </li>
            }
          </ul>
        </div>

        <p class="relative text-xs text-slate-500">© CHRISCO Constructora</p>
      </aside>

      <div class="flex min-h-full items-center justify-center p-6 sm:p-10">
        <section class="w-full" [class]="wide() ? 'max-w-lg' : 'max-w-sm'">
          <div class="mb-6 flex justify-center lg:hidden"><app-logo class="h-16" /></div>
          <h1 class="text-2xl font-extrabold tracking-tight text-slate-900">{{ title() }}</h1>
          @if (subtitle()) {
            <p class="mt-1.5 mb-7 text-sm text-slate-500">{{ subtitle() }}</p>
          } @else {
            <div class="mb-7"></div>
          }
          <ng-content />
        </section>
      </div>
    </main>
  `,
})
export class AuthCard {
  readonly title = input.required<string>();
  readonly subtitle = input('');
  readonly wide = input(false);
  protected readonly beneficios = BENEFICIOS;
}
