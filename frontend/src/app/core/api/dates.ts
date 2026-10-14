/**
 * Los `<input type="datetime-local">` entregan hora local sin zona ("2026-10-14T09:30"). La API
 * trabaja con instantes en UTC, así que se convierten aquí, en un solo lugar.
 */

export interface Periodo {
  desde: string;
  hasta: string;
}

/** Periodo válido (ambos extremos y fin posterior al inicio) a partir de dos inputs; si no, null. */
export function periodFromInputs(desde: string, hasta: string): Periodo | null {
  if (!desde || !hasta) return null;
  const start = new Date(desde);
  const end = new Date(hasta);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) return null;
  return { desde: start.toISOString(), hasta: end.toISOString() };
}

/** Convierte un instante a lo que espera un `<input type="datetime-local">` (hora local). */
export function toLocalInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
