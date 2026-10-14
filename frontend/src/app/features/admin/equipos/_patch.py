"""Parche temporal de la Fase 4 del frontend (se borra tras aplicarlo)."""
import sys

ROOT = sys.argv[1] + "/src/app"


def sub(path, old, new):
    full = f"{ROOT}/{path}"
    t = open(full, encoding="utf-8").read()
    assert old in t, (path, old[:70])
    open(full, "w", encoding="utf-8", newline="\n").write(t.replace(old, new, 1))


# ---- modelos
sub("core/api/models.ts", "  CategoriaAdminOut as CategoriaAdmin,", "  BloqueoOut as Bloqueo,\n  CategoriaAdminOut as CategoriaAdmin,")
sub("core/api/models.ts", "  CompanyUserOut as CompanyUser,", "  CompanyUserOut as CompanyUser,\n  DisponibilidadOut as Disponibilidad,")
sub("core/api/models.ts", "  EmpresaStatus,\n", "  EmpresaStatus,\n  EstadoActual,\n")
sub("core/api/models.ts", "  ImportResult,\n", "  ImportResult,\n  BloqueoIn,\n")

# ---- servicio del catálogo
p = "core/catalogo/catalogo.service.ts"
sub(p, "import { Categoria, EquipoCatalogo, Page } from '../api/models';", "import { Categoria, Disponibilidad, EquipoCatalogo, Page } from '../api/models';")
sub(p, "  categoria_id?: string;\n  limit?: number;", "  categoria_id?: string;\n  /** Con `desde` y `hasta` cada equipo indica si está libre en ese periodo. */\n  desde?: string;\n  hasta?: string;\n  solo_disponibles?: boolean;\n  limit?: number;")
sub(p, "  categorias(): Observable<Categoria[]> {", "  disponibilidad(id: string, desde: string, hasta: string): Observable<Disponibilidad> {\n    return this.http.get<Disponibilidad>(`${API_URL}/equipos/${id}/disponibilidad`, {\n      params: toParams({ desde, hasta }),\n    });\n  }\n\n  categorias(): Observable<Categoria[]> {")

# ---- servicio de equipos (personal)
p = "features/admin/equipos/equipos.service.ts"
sub(p, "import { Equipo, EquipoInput, EquipoStatus, Foto, ImportResult, Page } from '../../../core/api/models';", "import {\n  Bloqueo,\n  BloqueoIn,\n  Equipo,\n  EquipoInput,\n  EquipoStatus,\n  Foto,\n  ImportResult,\n  Page,\n} from '../../../core/api/models';")
sub(p, "  /** Con `dryRun`", "  bloqueos(id: string): Observable<Bloqueo[]> {\n    return this.http.get<Bloqueo[]>(`${this.base}/${id}/bloqueos`);\n  }\n\n  createBloqueo(id: string, body: BloqueoIn): Observable<Bloqueo> {\n    return this.http.post<Bloqueo>(`${this.base}/${id}/bloqueos`, body);\n  }\n\n  releaseBloqueo(bloqueoId: string): Observable<void> {\n    return this.http.post<void>(`${API_URL}/admin/bloqueos/${bloqueoId}/liberar`, {});\n  }\n\n  /** Con `dryRun`")

# ---- etiqueta de estado
p = "shared/status-badge/status-badge.ts"
sub(p, "import { EmpresaStatus, EquipoStatus } from '../../core/api/models';", "import { EmpresaStatus, EquipoStatus, EstadoActual } from '../../core/api/models';")
sub(p, "type Status = EmpresaStatus | EquipoStatus;", "type Status = EmpresaStatus | EquipoStatus | EstadoActual;")
sub(p, "  baja: { label: 'Baja', classes: 'bg-slate-200 text-slate-700' },", "  baja: { label: 'Baja', classes: 'bg-slate-200 text-slate-700' },\n  libre: { label: 'Libre', classes: GREEN },\n  bloqueado: { label: 'Bloqueado', classes: AMBER },\n  rentado: { label: 'Rentado', classes: 'bg-sky-100 text-sky-800' },")
sub(p, "/** Etiqueta de color para el estado de una empresa o de un equipo. */", "/** Etiqueta de color para el estado de una empresa o la situación de un equipo. */")

# ---- lista de equipos: situación actual
p = "features/admin/equipos/equipos-page.ts"
sub(p, '<td class="p-3"><app-status-badge [status]="e.status" /></td>', '<td class="p-3"><app-status-badge [status]="e.estado_actual" /></td>')
sub(p, '<th class="p-3">Estado</th>', '<th class="p-3">Situación</th>')

# ---- formulario del equipo: situación y bloqueos
p = "features/admin/equipos/equipo-form.ts"
sub(p, "import { EquiposService } from './equipos.service';", "import { StatusBadge } from '../../../shared/status-badge/status-badge';\nimport { EquipoBloqueos } from './equipo-bloqueos';\nimport { EquiposService } from './equipos.service';")
sub(p, "imports: [ReactiveFormsModule, RouterLink, SpecFields],", "imports: [ReactiveFormsModule, RouterLink, SpecFields, StatusBadge, EquipoBloqueos],")
print("ok")
