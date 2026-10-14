import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { Logo } from '../logo/logo';

/** Tarjeta centrada sobre fondo oscuro que usan todas las pantallas públicas (login, registro...). */
@Component({
  selector: 'app-auth-card',
  imports: [Logo],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="bg-chrisco-dark fixed inset-0 overflow-y-auto p-4">
      <div class="mx-auto flex min-h-full items-center justify-center">
        <section
          class="my-4 w-full rounded-2xl bg-white p-6 shadow-2xl"
          [class]="wide() ? 'max-w-lg' : 'max-w-sm'"
        >
          <div class="mb-4 flex justify-center"><app-logo class="h-20" /></div>
          <h1 class="text-center text-lg font-black">{{ title() }}</h1>
          @if (subtitle()) {
            <p class="mb-5 text-center text-xs text-slate-500">{{ subtitle() }}</p>
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
}
