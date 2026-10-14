/** Tipos de la API. Se generan de FastAPI (`npm run api:gen`); aquí solo se les da un nombre corto. */
export type {
  CategoriaAdminOut as CategoriaAdmin,
  CategoriaIn,
  CategoriaOut as Categoria,
  CompanyUserOut as CompanyUser,
  EmpresaDetailOut as EmpresaDetail,
  EmpresaListItem,
  EmpresaStatus,
  EquipoCatalogOut as EquipoCatalogo,
  EquipoOut as Equipo,
  EquipoStatus,
  EquipoUpdate as EquipoInput,
  FotoOut as Foto,
  ImportResult,
  Role,
  SpecField,
  SpecFieldType,
  TokenPair,
  UserOut as User,
} from './generated';

/** Una página de resultados (la API las devuelve como `{ items, total }`). */
export interface Page<T> {
  items: T[];
  total: number;
}
