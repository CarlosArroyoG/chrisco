/** Arma un multipart (campos de texto + un PDF) para los endpoints que reciben archivos. */
export function toFormData(fields: Record<string, string>, constancia: File): FormData {
  const body = new FormData();
  for (const [key, value] of Object.entries(fields)) body.append(key, value);
  body.append('constancia', constancia);
  return body;
}
