import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';
import { ROLE_LABEL } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import { Logo } from '../shared/logo/logo';

/** Marco común de las pantallas autenticadas: barra superior y área de contenido. */
@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, Logo],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header
      class="bg-chrisco-dark border-chrisco-slate sticky top-0 z-40 border-b text-white shadow-md"
    >
      <div class="mx-auto flex h-16 max-w-7xl items-center justify-between px-4">
        <app-logo [onDark]="true" class="h-10" />
        <div class="flex items-center gap-3">
          @if (auth.user(); as user) {
            <span
              class="bg-chrisco-orange/20 border-chrisco-orange/30 rounded-full border px-2.5 py-1 text-xs font-bold text-orange-400"
            >
              {{ roleLabel[user.role] }}
            </span>
          }
          <button
            type="button"
            (click)="logout()"
            class="p-2 text-xs font-semibold text-slate-300 hover:text-rose-400"
          >
            Salir
          </button>
        </div>
      </div>
    </header>
    <main class="mx-auto w-full max-w-7xl p-3 sm:p-6">
      <router-outlet />
    </main>
  `,
})
export class Shell {
  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  protected readonly roleLabel = ROLE_LABEL;

  protected logout(): void {
    this.auth.logout();
    void this.router.navigate(['/login']);
  }
}
