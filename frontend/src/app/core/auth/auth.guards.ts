import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Role } from '../api/models';
import { HOME_BY_ROLE } from './auth.models';
import { AuthService } from './auth.service';

/** Exige sesión iniciada. */
export const authGuard: CanActivateFn = () => {
  const router = inject(Router);
  return inject(AuthService).isAuthenticated() ? true : router.createUrlTree(['/login']);
};

/** Para el login: si ya hay sesión, manda al usuario a su inicio. */
export const guestGuard: CanActivateFn = () => {
  const user = inject(AuthService).user();
  return user ? inject(Router).createUrlTree([HOME_BY_ROLE[user.role]]) : true;
};

/** Ruta raíz: lleva a cada rol a su inicio. */
export const homeRedirectGuard: CanActivateFn = () => {
  const user = inject(AuthService).user();
  const router = inject(Router);
  return router.createUrlTree([user ? HOME_BY_ROLE[user.role] : '/login']);
};

/** Exige uno de los roles dados; si no, devuelve al usuario a su propio inicio. */
export const roleGuard =
  (...roles: Role[]): CanActivateFn =>
  () => {
    const user = inject(AuthService).user();
    const router = inject(Router);
    if (!user) return router.createUrlTree(['/login']);
    return roles.includes(user.role) ? true : router.createUrlTree([HOME_BY_ROLE[user.role]]);
  };
