import { HttpErrorResponse } from '@angular/common/http';

const FIELD_LABELS: Record<string, string> = {
  razon_social: 'Razón social',
  sitio_web: 'Sitio web',
  rfc: 'RFC',
  full_name: 'Nombre',
  email: 'Correo',
  password: 'Contraseña',
  constancia: 'Constancia',
  motivo: 'Motivo',
};

const TYPE_TEXT: Record<string, string> = {
  missing: 'es obligatorio',
  string_too_short: 'es demasiado corto',
  string_too_long: 'es demasiado largo',
};

interface ValidationItem {
  type: string;
  loc: (string | number)[];
  msg: string;
}

function validationText(item: ValidationItem): string {
  const field = FIELD_LABELS[String(item.loc.at(-1))];
  const text =
    item.type === 'value_error'
      ? item.msg.replace(/^Value error, /, '')
      : (TYPE_TEXT[item.type] ?? 'no es válido');
  return field ? `${field}: ${text}` : text;
}

/** Convierte un error de la API en un mensaje en español para mostrar al usuario. */
export function apiErrorMessage(err: unknown, fallback: string): string {
  if (!(err instanceof HttpErrorResponse)) return fallback;
  if (err.status === 0) return 'No hay conexión con el servidor. Revisa tu internet.';
  if (err.status === 429) return 'Demasiados intentos. Espera un momento e inténtalo de nuevo.';
  const detail: unknown = err.error?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length) return validationText(detail[0] as ValidationItem);
  return fallback;
}
