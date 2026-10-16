import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ROLE_LABEL } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import { Icon, IconName } from '../shared/icon/icon';
import { Logo } from '../shared/logo/logo';

interface NavItem {
  path: string;
  label: string;
  icon: IconName;
  /** `exact` evita que «Empresas» (/admin) quede activa en todas las secciones. */
  exact: boolean;
  adminOnly?: boolean;
}

/** Secciones del personal (admin y ventas). */
const STAFF_NAV: NavItem[] = [
  { path: '/admin', label: 'Empresas', icon: 'empresas', exact: true },
  { path: '/admin/rentas', label: 'Rentas', icon: 'rentas', exact: false },
  { path: '/admin/cobranza', label: 'Cobranza', icon: 'cobranza', exact: false },
  { path: '/admin/mantenimiento', label: 'Mantenimiento', icon: 'mantenimiento', exact: false },
  { path: '/admin/equipos', label: 'Equipos', icon: 'equipos', exact: false },
  { path: '/admin/categorias', label: 'Categorías', icon: 'categorias', exact: false },
  { path: '/admin/personal', label: 'Personal', icon: 'personal', exact: false, adminOnly: true },
];

const CLIENT_NAV: NavItem[] = [
  { path: '/cliente', label: 'Mi empresa', icon: 'casa', exact: true },
  { path: '/cliente/catalogo', label: 'Catálogo', icon: 'catalogo', exact: false },
  { path: '/cliente/rentas', label: 'Mis rentas', icon: 'rentas', exact: false },
];

/** Marco común de las pantallas autenticadas: menú lateral (personal) o barra superior. */
@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Logo, Icon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (isStaff()) {
      <aside
        class="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col bg-linear-to-b from-[#1a2227] to-[#222e35] text-slate-300 lg:flex"
      >
        <div class="px-6 pt-6 pb-4"><app-logo [onDark]="true" class="h-14" /></div>
        <nav class="mt-2 flex-1 space-y-1 px-3" aria-label="Secciones">
          @for (item of nav(); track item.path) {
            <a
              [routerLink]="item.path"
              routerLinkActive="bg-white/10 text-white"
              #rla="routerLinkActive"
              [routerLinkActiveOptions]="{ exact: item.exact }"
              class="group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition hover:bg-white/5 hover:text-white"
            >
              <app-icon
                [name]="item.icon"
                class="size-5 transition"
                [class]="
                  rla.isActive ? 'text-chrisco-orange' : 'text-slate-400 group-hover:text-slate-200'
                "
              />
              {{ item.label }}
            </a>
          }
        </nav>
        <div class="m-3 rounded-2xl bg-white/5 p-3">
          <div class="flex items-center gap-3">
            <span
              class="from-chrisco-orange grid size-9 shrink-0 place-items-center rounded-full bg-linear-to-br to-orange-600 text-sm font-bold text-white"
              >{{ initial() }}</span
            >
            <div class="min-w-0">
              <p class="truncate text-sm font-semibold text-white">{{ auth.user()?.full_name }}</p>
              <p class="text-xs text-slate-400">{{ roleText() }}</p>
            </div>
          </div>
          <button
            type="button"
            (click)="logout()"
            class="mt-3 flex w-full items-center justify-center gap-2 rounded-lg py-1.5 text-xs font-semibold text-slate-300 transition hover:bg-white/10 hover:text-white"
          >
            <app-icon name="salir" class="size-4" /> Salir
          </button>
        </div>
      </aside>

      <header class="bg-chrisco-dark sticky top-0 z-40 text-white shadow-md lg:hidden">
        <div class="flex h-14 items-center justify-between px-4">
          <app-logo [onDark]="true" class="h-9" />
          <button type="button" (click)="logout()" class="text-xs font-semibold text-slate-300">
            Salir
          </button>
        </div>
        <nav class="flex gap-1 overflow-x-auto px-3 pb-2" aria-label="Secciones">
          @for (item of nav(); track item.path) {
            <a
              [routerLink]="item.path"
              routerLinkActive="bg-white/15 text-white"
              [routerLinkActiveOptions]="{ exact: item.exact }"
              class="rounded-full px-3 py-1.5 text-xs font-semibold whitespace-nowrap text-slate-300"
            >
              {{ item.label }}
            </a>
          }
        </nav>
      </header>

      <main class="lg:pl-64">
        <div class="mx-auto w-full max-w-6xl px-4 py-6 sm:px-8 sm:py-8">
          <router-outlet />
        </div>
      </main>
    } @else {
      <header class="sticky top-0 z-40 border-b border-slate-200/70 bg-white/80 backdrop-blur-lg">
        <div class="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-8">
          <div class="flex items-center gap-8">
            <app-logo class="h-10" />
            @if (isClient()) {
              <nav class="hidden items-center gap-1 sm:flex" aria-label="Secciones">
                @for (item of nav(); track item.path) {
                  <a
                    [routerLink]="item.path"
                    routerLinkActive="bg-orange-50 text-chrisco-orange-dark"
                    [routerLinkActiveOptions]="{ exact: item.exact }"
                    class="rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100"
                  >
                    {{ item.label }}
                  </a>
                }
              </nav>
            }
          </div>
          <div class="flex items-center gap-3">
            <span
              class="from-chrisco-orange grid size-9 place-items-center rounded-full bg-linear-to-br to-orange-600 text-sm font-bold text-white"
              >{{ initial() }}</span
            >
            <div class="hidden text-right leading-tight sm:block">
              <p class="text-sm font-semibold text-slate-800">{{ auth.user()?.full_name }}</p>
              <p class="text-xs text-slate-500">{{ roleText() }}</p>
            </div>
            <button type="button" (click)="logout()" class="btn-secondary px-3 py-2 text-xs">
              Salir
            </button>
          </div>
        </div>
        @if (isClient()) {
          <nav
            class="flex gap-1 overflow-x-auto border-t border-slate-100 px-3 py-1.5 sm:hidden"
            aria-label="Secciones"
          >
            @for (item of nav(); track item.path) {
              <a
                [routerLink]="item.path"
                routerLinkActive="bg-orange-50 text-chrisco-orange-dark"
                [routerLinkActiveOptions]="{ exact: item.exact }"
                class="rounded-full px-3 py-1.5 text-xs font-semibold whitespace-nowrap text-slate-600"
              >
                {{ item.label }}
              </a>
            }
          </nav>
        }
      </header>
      <main class="mx-auto w-full max-w-6xl px-4 py-6 sm:px-8 sm:py-8">
        <router-outlet />
      </main>
    }
  `,
})
export class Shell {
  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly isStaff = computed(() => {
    const role = this.auth.user()?.role;
    return role === 'admin' || role === 'ventas';
  });
  protected readonly isClient = computed(() => this.auth.user()?.role === 'cliente');
  protected readonly nav = computed(() => {
    if (this.isClient()) return CLIENT_NAV;
    const role = this.auth.user()?.role;
    return STAFF_NAV.filter((item) => !item.adminOnly || role === 'admin');
  });
  protected readonly initial = computed(() =>
    (this.auth.user()?.full_name ?? '?').trim().charAt(0).toUpperCase(),
  );
  protected readonly roleText = computed(() => {
    const role = this.auth.user()?.role;
    return role ? ROLE_LABEL[role] : '';
  });

  protected logout(): void {
    this.auth.logout();
    void this.router.navigate(['/login']);
  }
}
