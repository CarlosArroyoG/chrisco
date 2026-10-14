import path from 'node:path';

/** Configuración compartida por la suite: puertos, base de datos y archivos temporales. */
export const API_PORT = 8011;
export const WEB_PORT = 4201;
export const WEB_URL = `http://localhost:${WEB_PORT}`;
export const TMP_DIR = path.join(__dirname, '.tmp');
export const OUTBOX_FILE = path.join(TMP_DIR, 'outbox.jsonl');

export const DATABASE_URL =
  process.env['E2E_DATABASE_URL'] ??
  'postgresql+psycopg://chrisco:chrisco_dev@localhost:5433/chrisco_e2e';

export const BACKEND_ENV = {
  DATABASE_URL,
  SECRET_KEY: 'clave-solo-para-e2e-0123456789abcdef0123456789abcdef',
  MAIL_BACKEND: 'file',
  MAIL_OUTBOX_FILE: OUTBOX_FILE,
  UPLOADS_DIR: path.join(TMP_DIR, 'uploads'),
  RATE_LIMIT_ENABLED: 'false',
  FRONTEND_URL: WEB_URL,
  SALES_WHATSAPP_NUMBER: '5217221234567',
  CORS_ORIGINS: JSON.stringify([WEB_URL]),
};

export const ADMIN = { email: 'admin@e2e-chrisco.com', password: 'admin-e2e-clave-123', name: 'Admin E2E' };
export const VENTAS = { email: 'ventas@e2e-chrisco.com', password: 'ventas-e2e-clave-123', name: 'Ventas E2E' };
