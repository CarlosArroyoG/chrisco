import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  CanActivateFn,
  Router,
  RouterStateSnapshot,
  UrlTree,
} from '@angular/router';
import { authGuard, guestGuard, homeRedirectGuard, roleGuard } from './auth.guards';
import { Role } from './auth.models';
import { AuthService } from './auth.service';

describe('guards', () => {
  let auth: AuthService;
  let router: Router;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [{ provide: Router, useValue: realRouter() }] });
    auth = TestBed.inject(AuthService);
    router = TestBed.inject(Router);
  });

  function realRouter(): Pick<Router, 'createUrlTree' | 'serializeUrl'> {
    return {
      createUrlTree: (commands) => ({ toString: () => (commands as string[]).join('') }) as UrlTree,
      serializeUrl: (tree) => tree.toString(),
    };
  }

  function run(guard: CanActivateFn): boolean | string {
    const result = TestBed.runInInjectionContext(() =>
      guard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
    );
    return typeof result === 'boolean' ? result : router.serializeUrl(result as UrlTree);
  }

  function loginAs(role: Role): void {
    auth.user.set({ id: '1', email: 'a@b.com', full_name: 'Ana', role });
  }

  it('authGuard: sin sesión manda a /login', () => {
    expect(run(authGuard)).toBe('/login');
  });

  it('authGuard: con sesión deja pasar', () => {
    loginAs('cliente');
    expect(run(authGuard)).toBe(true);
  });

  it('guestGuard: con sesión manda al inicio del rol', () => {
    loginAs('operador');
    expect(run(guestGuard)).toBe('/operador');
  });

  it('guestGuard: sin sesión deja ver el login', () => {
    expect(run(guestGuard)).toBe(true);
  });

  it('homeRedirectGuard: ventas va a /admin', () => {
    loginAs('ventas');
    expect(run(homeRedirectGuard)).toBe('/admin');
  });

  it('roleGuard: rol permitido pasa', () => {
    loginAs('admin');
    expect(run(roleGuard('admin', 'ventas'))).toBe(true);
  });

  it('roleGuard: rol no permitido vuelve a su propio inicio', () => {
    loginAs('cliente');
    expect(run(roleGuard('admin', 'ventas'))).toBe('/cliente');
  });

  it('roleGuard: sin sesión manda a /login', () => {
    expect(run(roleGuard('admin'))).toBe('/login');
  });
});
