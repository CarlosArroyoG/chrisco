import { resetDatabase } from './db';

/** Deja la base creada y migrada antes de la primera prueba (cada archivo la reinicia además). */
export default function globalSetup(): void {
  resetDatabase();
}
