import { Routes } from '@angular/router';
import { authGuard, guestGuard, homeRedirectGuard, roleGuard } from './core/auth/auth.guards';

export const routes: Routes = [
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/login/login').then((m) => m.Login),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./layout/shell').then((m) => m.Shell),
    children: [
      { path: '', pathMatch: 'full', canActivate: [homeRedirectGuard], children: [] },
      {
        path: 'admin',
        canActivate: [roleGuard('admin', 'ventas')],
        loadComponent: () => import('./features/admin/admin-home').then((m) => m.AdminHome),
      },
      {
        path: 'operador',
        canActivate: [roleGuard('operador')],
        loadComponent: () =>
          import('./features/operador/operador-home').then((m) => m.OperadorHome),
      },
      {
        path: 'cliente',
        canActivate: [roleGuard('cliente')],
        loadComponent: () => import('./features/cliente/cliente-home').then((m) => m.ClienteHome),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
