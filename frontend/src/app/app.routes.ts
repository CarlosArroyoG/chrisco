import { Routes } from '@angular/router';
import { authGuard, guestGuard, homeRedirectGuard, roleGuard } from './core/auth/auth.guards';

export const routes: Routes = [
  // Públicas
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/login/login').then((m) => m.Login),
  },
  {
    path: 'registro',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/register').then((m) => m.Register),
  },
  {
    path: 'olvide-contrasena',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/forgot-password').then((m) => m.ForgotPassword),
  },
  // Enlaces que llegan por correo: funcionan con o sin sesión abierta.
  {
    path: 'verificar-correo',
    loadComponent: () => import('./features/auth/verify-email').then((m) => m.VerifyEmail),
  },
  {
    path: 'aceptar-invitacion',
    data: { mode: 'invite' },
    loadComponent: () => import('./features/auth/set-password').then((m) => m.SetPassword),
  },
  {
    path: 'recuperar-contrasena',
    data: { mode: 'reset' },
    loadComponent: () => import('./features/auth/set-password').then((m) => m.SetPassword),
  },
  // Autenticadas
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./layout/shell').then((m) => m.Shell),
    children: [
      { path: '', pathMatch: 'full', canActivate: [homeRedirectGuard], children: [] },
      {
        path: 'admin',
        canActivate: [roleGuard('admin', 'ventas')],
        children: [
          {
            path: '',
            loadComponent: () => import('./features/admin/admin-home').then((m) => m.AdminHome),
          },
          {
            path: 'empresas/:id',
            loadComponent: () =>
              import('./features/admin/empresa-review').then((m) => m.EmpresaReview),
          },
          {
            path: 'equipos',
            loadComponent: () =>
              import('./features/admin/equipos/equipos-page').then((m) => m.EquiposPage),
          },
          // Las rutas fijas van antes que `:id` para que no se lean como un id.
          {
            path: 'equipos/nuevo',
            loadComponent: () =>
              import('./features/admin/equipos/equipo-form').then((m) => m.EquipoForm),
          },
          {
            path: 'equipos/importar',
            loadComponent: () =>
              import('./features/admin/equipos/equipos-import').then((m) => m.EquiposImport),
          },
          {
            path: 'equipos/:id',
            loadComponent: () =>
              import('./features/admin/equipos/equipo-form').then((m) => m.EquipoForm),
          },
          {
            path: 'rentas',
            loadComponent: () => import('./features/rentas/rentas-page').then((m) => m.RentasPage),
          },
          {
            path: 'rentas/:id',
            loadComponent: () =>
              import('./features/rentas/renta-detalle').then((m) => m.RentaDetalle),
          },
          {
            path: 'cobranza',
            loadComponent: () =>
              import('./features/admin/cobranza/cobranza-page').then((m) => m.CobranzaPage),
          },
          {
            path: 'categorias',
            loadComponent: () =>
              import('./features/admin/categorias/categorias-page').then((m) => m.CategoriasPage),
          },
        ],
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
        children: [
          {
            path: '',
            loadComponent: () =>
              import('./features/cliente/cliente-home').then((m) => m.ClienteHome),
          },
          {
            path: 'catalogo',
            loadComponent: () =>
              import('./features/cliente/catalogo/catalogo-page').then((m) => m.CatalogoPage),
          },
          {
            path: 'rentas',
            loadComponent: () => import('./features/rentas/rentas-page').then((m) => m.RentasPage),
          },
          {
            path: 'rentas/:id',
            loadComponent: () =>
              import('./features/rentas/renta-detalle').then((m) => m.RentaDetalle),
          },
          {
            path: 'catalogo/:id',
            loadComponent: () =>
              import('./features/cliente/catalogo/catalogo-detalle').then((m) => m.CatalogoDetalle),
          },
        ],
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
