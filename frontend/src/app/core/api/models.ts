/** Tipos de la API. Se generan de FastAPI (`npm run api:gen`); aquí solo se les da un nombre corto. */
export type {
  BloqueoOut as Bloqueo,
  CategoriaAdminOut as CategoriaAdmin,
  CategoriaIn,
  CategoriaOut as Categoria,
  CompanyUserOut as CompanyUser,
  DisponibilidadOut as Disponibilidad,
  EmpresaDetailOut as EmpresaDetail,
  EmpresaListItem,
  EmpresaStatus,
  EstadoActual,
  EquipoCatalogOut as EquipoCatalogo,
  EquipoOut as Equipo,
  EquipoStatus,
  EquipoUpdate as EquipoInput,
  FotoOut as Foto,
  ImportResult,
  Ocupacion,
  BloqueoIn,
  OperadorModo,
  PreviewOut as SolicitudPreview,
  RentaEstado,
  RentaOut as Renta,
  Requisito,
  Role,
  SpecField,
  SolicitudCreada,
  SolicitudIn,
  SpecFieldType,
  Transporte,
  TokenPair,
  WhatsappOut as Whatsapp,
  UserOut as User,
} from './generated';

/** Una página de resultados (la API las devuelve como `{ items, total }`). */
export interface Page<T> {
  items: T[];
  total: number;
}
