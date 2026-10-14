import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { ADMIN, BACKEND_ENV, TMP_DIR, VENTAS } from './env';

const BACKEND = path.join(__dirname, '..', 'backend');

function uv(...args: string[]): void {
  execFileSync('uv', ['run', ...args], {
    cwd: BACKEND,
    env: { ...process.env, ...BACKEND_ENV, PYTHONPATH: BACKEND },
    stdio: 'inherit',
  });
}

/**
 * Deja el sistema como recién instalado: base de datos vacía y migrada, buzón y archivos
 * limpios, y dos usuarios del personal. Cada archivo de pruebas lo llama al empezar para no
 * depender de lo que dejó otro.
 */
export function resetDatabase(): void {
  fs.rmSync(TMP_DIR, { recursive: true, force: true });
  fs.mkdirSync(TMP_DIR, { recursive: true });

  uv('python', path.join(__dirname, 'scripts', 'prepare_db.py'));
  for (const [user, role] of [
    [ADMIN, 'admin'],
    [VENTAS, 'ventas'],
  ] as const) {
    uv('python', '-m', 'app.cli', 'create-user', '--email', user.email, '--name', user.name,
      '--role', role, '--password', user.password);
  }
}
