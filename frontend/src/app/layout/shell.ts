import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ROLE_LABEL } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import { Logo } from '../shared/logo/logo';

/** Secciones del personal (admin y ventas). `exact` evita que «Empresas» quede activa en todas. */
const STAFF_NAV: { path: string; label: string; exact: boolean; adminOnly?: boolean }[] = [
  { path: '/admin', label: 'Empresas', exact: true },
  { path: '/admin/rentas', label: 'Rentas', exact: false },
  { path: '/admin/cobranza', label: 'Cobranza', exact: false },
  { path: '/admin/mantenimiento', label: 'Mantenimiento', exact: false },
  { path: '/admin/equipos', label: 'Equipos', exact: false },
  { path: '/admin/categorias', label: 'Categorías', exact: false },
  { path: '/admin/personal', label: 'Personal', exact: false, adminOnly: true },
];

/** Marco común de las pantallas autenticadas: barra superior, navegación y área de contenido. */
@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Logo],
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
      @if (isStaff()) {
        <nav class="bg-chrisco-charcoal" aria-label="Secciones">
          <div class="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4">
            @for (item of nav(); track item.path) {
              <a
                [routerLink]="item.path"
                routerLinkActive="border-chrisco-orange text-white"
                [routerLinkActiveOptions]="{ exact: item.exact }"
                class="border-b-2 border-transparent px-3 py-2 text-xs font-bold whitespace-nowrap text-slate-300 hover:text-white"
              >
                {{ item.label }}
              </a>
            }
          </div>
        </nav>
      }
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
  protected readonly nav = computed(() =>
    STAFF_NAV.filter((item) => !item.adminOnly || this.auth.user()?.role === 'admin'),
  );
  protected readonly isStaff = computed(() => {
    const role = this.auth.user()?.role;
    return role === 'admin' || role === 'ventas';
  });

  protected logout(): void {
    this.auth.logout();
    void this.router.navigate(['/login']);
  }
}
