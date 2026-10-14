import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import {
  Observable,
  catchError,
  finalize,
  map,
  of,
  shareReplay,
  switchMap,
  tap,
  throwError,
} from 'rxjs';
import { TokenPair, User } from './auth.models';

/** Base de la API. En desarrollo la reescribe proxy.conf.json; en producción, el proxy inverso. */
export const API_URL = '/api';

const REFRESH_KEY = 'chrisco.refresh_token';

/**
 * Sesión del usuario. El access token vive solo en memoria; el refresh token se guarda en
 * localStorage para sobrevivir recargas (compromiso aceptado para una PWA: ver docs/ESTADO.md).
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private accessToken: string | null = null;
  private refreshInFlight$: Observable<TokenPair> | null = null;

  readonly user = signal<User | null>(null);
  readonly isAuthenticated = computed(() => this.user() !== null);

  get token(): string | null {
    return this.accessToken;
  }

  login(email: string, password: string): Observable<User> {
    return this.http.post<TokenPair>(`${API_URL}/auth/login`, { email, password }).pipe(
      tap((tokens) => this.storeTokens(tokens)),
      switchMap(() => this.loadUser()),
    );
  }

  /** Se ejecuta al arrancar la app: recupera la sesión si hay un refresh token vigente. */
  restoreSession(): Observable<void> {
    if (!readRefreshToken()) return of(undefined);
    return this.refresh().pipe(
      switchMap(() => this.loadUser()),
      map(() => undefined),
      catchError(() => {
        this.logout();
        return of(undefined);
      }),
    );
  }

  /** Renueva los tokens. Varias llamadas simultáneas comparten una sola petición. */
  refresh(): Observable<TokenPair> {
    if (this.refreshInFlight$) return this.refreshInFlight$;
    const refreshToken = readRefreshToken();
    if (!refreshToken) return throwError(() => new Error('No hay sesión que renovar'));

    this.refreshInFlight$ = this.http
      .post<TokenPair>(`${API_URL}/auth/refresh`, { refresh_token: refreshToken })
      .pipe(
        tap((tokens) => this.storeTokens(tokens)),
        finalize(() => (this.refreshInFlight$ = null)),
        shareReplay(1),
      );
    return this.refreshInFlight$;
  }

  logout(): void {
    this.accessToken = null;
    this.user.set(null);
    try {
      localStorage.removeItem(REFRESH_KEY);
    } catch {
      /* almacenamiento no disponible: no hay nada que borrar */
    }
  }

  private loadUser(): Observable<User> {
    return this.http.get<User>(`${API_URL}/auth/me`).pipe(tap((user) => this.user.set(user)));
  }

  private storeTokens(tokens: TokenPair): void {
    this.accessToken = tokens.access_token;
    try {
      localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
    } catch {
      /* sin almacenamiento la sesión dura hasta recargar la página */
    }
  }
}

function readRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}
