import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';
import { API_URL, AuthService } from './auth.service';

const PUBLIC_ENDPOINTS = [`${API_URL}/auth/login`, `${API_URL}/auth/refresh`];

/** Agrega el access token y, ante un 401, renueva la sesión y repite la petición una vez. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (!req.url.startsWith(API_URL) || PUBLIC_ENDPOINTS.includes(req.url)) return next(req);

  const withToken = (r: HttpRequest<unknown>) =>
    auth.token ? r.clone({ setHeaders: { Authorization: `Bearer ${auth.token}` } }) : r;

  return next(withToken(req)).pipe(
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse) || error.status !== 401) {
        return throwError(() => error);
      }
      return auth.refresh().pipe(
        switchMap(() => next(withToken(req))),
        catchError((refreshError: unknown) => {
          auth.logout();
          void router.navigate(['/login']);
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
