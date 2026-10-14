export type Role = 'admin' | 'ventas' | 'operador' | 'cliente';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

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
