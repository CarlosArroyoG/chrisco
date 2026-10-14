import fs from 'node:fs';
import { OUTBOX_FILE } from '../env';

interface Mail {
  to: string;
  subject: string;
  body: string;
}

function readOutbox(): Mail[] {
  if (!fs.existsSync(OUTBOX_FILE)) return [];
  return fs
    .readFileSync(OUTBOX_FILE, 'utf-8')
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line) as Mail);
}

/** Espera el correo más reciente para `to` cuyo asunto contiene `subject` y devuelve su enlace. */
export async function linkFromMail(to: string, subject: string, timeoutMs = 10_000): Promise<string> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const mail = readOutbox()
      .filter((m) => m.to === to && m.subject.includes(subject))
      .at(-1);
    const link = mail?.body.match(/https?:\/\/\S+/)?.[0];
    if (link) return link;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`No llegó un correo "${subject}" para ${to}`);
}

export function mailsTo(to: string): Mail[] {
  return readOutbox().filter((m) => m.to === to);
}
