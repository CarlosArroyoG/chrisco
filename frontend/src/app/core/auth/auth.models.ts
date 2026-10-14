import { Role } from '../api/models';

/** Ruta de inicio de cada rol. Única fuente de verdad para redirecciones. */
export const HOME_BY_ROLE: Record<Role, string> = {
  admin: '/admin',
  ventas: '/admin',
  operador: '/operador',
  cliente: '/cliente',
};

export const ROLE_LABEL: Record<Role, string> = {
  admin: 'Administrador',
  ventas: 'Ventas',
  operador: 'Operador',
  cliente: 'Cliente',
};
