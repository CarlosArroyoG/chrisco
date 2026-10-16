import { RentaEstado } from '../api/models';

export type EtapaTono = 'sky' | 'amber' | 'emerald' | 'orange' | 'slate' | 'rose';

export interface Etapa {
  /** Cómo se llama la etapa para el cliente. */
  etiqueta: string;
  /** Texto del botón principal en esa etapa. */
  accion: string;
  /** Qué sigue, en una frase. */
  pista: string;
  tono: EtapaTono;
}

/** Lo que el cliente ve y puede hacer en cada etapa de una renta. Única fuente de esos textos. */
export const ETAPAS: Record<RentaEstado, Etapa> = {
  solicitada: {
    etiqueta: 'Solicitud enviada',
    accion: 'Ver mi solicitud',
    pista: 'Ventas está preparando tu cotización.',
    tono: 'amber',
  },
  cotizada: {
    etiqueta: 'Cotización lista',
    accion: 'Revisar cotización',
    pista: 'Acéptala para apartar el equipo.',
    tono: 'sky',
  },
  apartada: {
    etiqueta: 'Equipo apartado',
    accion: 'Completar requisitos y pagar',
    pista: 'Sube tus documentos y deposita el anticipo.',
    tono: 'orange',
  },
  confirmada: {
    etiqueta: 'Renta confirmada',
    accion: 'Ver mi renta',
    pista: 'Todo en regla: te entregamos el equipo.',
    tono: 'emerald',
  },
  en_renta: {
    etiqueta: 'En renta',
    accion: 'Ver mi renta',
    pista: 'El equipo está en tu obra.',
    tono: 'emerald',
  },
  devuelta: {
    etiqueta: 'Devuelta',
    accion: 'Ver detalle',
    pista: 'Recibimos el equipo; queda cerrar la cuenta.',
    tono: 'slate',
  },
  cerrada: {
    etiqueta: 'Cerrada',
    accion: 'Ver detalle',
    pista: 'Renta terminada y pagada.',
    tono: 'slate',
  },
  vencida: {
    etiqueta: 'Vencida',
    accion: 'Ver detalle',
    pista: 'La reserva venció y el equipo se liberó.',
    tono: 'slate',
  },
  cancelada: {
    etiqueta: 'Cancelada',
    accion: 'Ver detalle',
    pista: 'Esta solicitud se canceló.',
    tono: 'slate',
  },
  rechazada: {
    etiqueta: 'No atendida',
    accion: 'Ver detalle',
    pista: 'Ventas no pudo atender esta solicitud.',
    tono: 'rose',
  },
};

/** Clases de color de una etiqueta según el tono. */
export const TONO_CLASES: Record<EtapaTono, string> = {
  sky: 'bg-sky-50 text-sky-700 ring-sky-200',
  amber: 'bg-amber-50 text-amber-700 ring-amber-200',
  emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  orange: 'bg-orange-50 text-orange-700 ring-orange-200',
  slate: 'bg-slate-100 text-slate-600 ring-slate-200',
  rose: 'bg-rose-50 text-rose-700 ring-rose-200',
};

/** Rentas que siguen su curso (se muestran en «activas»). */
export const ESTADOS_ABIERTOS: RentaEstado[] = [
  'solicitada',
  'cotizada',
  'apartada',
  'confirmada',
  'en_renta',
];
