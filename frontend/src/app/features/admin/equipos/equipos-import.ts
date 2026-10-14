import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../../core/api/errors';
import { saveBlob } from '../../../core/api/download';
import { Categoria, ImportResult } from '../../../core/api/models';
import { CatalogoService } from '../../../core/catalogo/catalogo.service';
import { EquiposService } from './equipos.service';

/** Carga masiva de equipos desde CSV: se valida primero y solo se guarda si todo está bien. */
@Component({
  selector: 'app-equipos-import',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a routerLink="/admin/equipos" class="link text-xs">← Volver a equipos</a>
    <h1 class="mt-2 text-lg font-black">Importar equipos desde CSV</h1>

    <section class="card mt-3 space-y-3">
      <h2 class="text-sm font-black">1. Descarga la plantilla</h2>
      <p class="text-xs text-slate-500">
        Una fila por equipo. Si eliges una categoría, la plantilla incluye una columna
        <code>spec_…</code> por cada una de sus especificaciones. Excel puede guardarla como CSV.
      </p>
      <div class="flex flex-wrap items-end gap-2">
        <div class="min-w-48">
          <label for="plantilla-categoria" class="label">Categoría (opcional)</label>
          <select id="plantilla-categoria" #categoria class="input">
            <option value="">Sin especificaciones</option>
            @for (c of categorias(); track c.id) {
              <option [value]="c.id">{{ c.nombre }}</option>
            }
          </select>
        </div>
        <button type="button" class="btn-secondary" (click)="downloadTemplate(categoria.value)">
          Descargar plantilla
        </button>
      </div>
    </section>

    <section class="card mt-4 space-y-3">
      <h2 class="text-sm font-black">2. Sube tu archivo</h2>
      <input
        id="archivo"
        type="file"
        accept=".csv,text/csv"
        aria-label="Archivo CSV"
        (change)="onFile($event)"
        class="w-full text-xs"
      />
      @if (error()) {
        <p role="alert" class="alert-error">{{ error() }}</p>
      }
      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          class="btn-secondary"
          [disabled]="!file() || busy()"
          (click)="run(true)"
        >
          Validar archivo
        </button>
        <button
          type="button"
          class="btn-primary"
          [disabled]="!canImport() || busy()"
          (click)="run(false)"
        >
          Importar {{ preview()?.rows ?? '' }} equipos
        </button>
      </div>
    </section>

    @if (preview(); as result) {
      <section class="card mt-4">
        @if (result.errors.length) {
          <p role="alert" class="alert-error">
            Hay {{ result.errors.length }} problema(s). No se guardó nada: corrige el archivo y
            vuelve a validar.
          </p>
          <table class="mt-3 w-full text-left text-xs">
            <thead class="text-[10px] font-bold text-slate-500 uppercase">
              <tr>
                <th class="w-16 py-1">Fila</th>
                <th class="py-1">Problema</th>
              </tr>
            </thead>
            <tbody class="divide-y">
              @for (e of result.errors; track $index) {
                <tr>
                  <td class="py-1.5 font-mono">{{ e.row }}</td>
                  <td class="py-1.5">{{ e.message }}</td>
                </tr>
              }
            </tbody>
          </table>
        } @else if (result.created) {
          <p role="status" class="alert-ok">
            Se importaron {{ result.created }} equipos.
            <a routerLink="/admin/equipos" class="link">Ver la lista</a>
          </p>
        } @else {
          <p role="status" class="alert-ok">
            El archivo es válido: {{ result.rows }} equipos listos. Pulsa «Importar» para
            guardarlos.
          </p>
        }
      </section>
    }
  `,
})
export class EquiposImport implements OnInit {
  private readonly service = inject(EquiposService);
  private readonly catalogo = inject(CatalogoService);

  protected readonly categorias = signal<Categoria[]>([]);
  protected readonly file = signal<File | null>(null);
  protected readonly preview = signal<ImportResult | null>(null);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.catalogo.categorias().subscribe((categorias) => this.categorias.set(categorias));
  }

  /** Solo se puede importar un archivo que ya se validó sin errores. */
  protected canImport(): boolean {
    const result = this.preview();
    return !!result && result.dry_run && result.rows > 0 && result.errors.length === 0;
  }

  protected onFile(event: Event): void {
    this.file.set((event.target as HTMLInputElement).files?.[0] ?? null);
    this.preview.set(null); // otro archivo exige validar de nuevo
    this.error.set(null);
  }

  protected downloadTemplate(categoriaId: string): void {
    this.service.template(categoriaId || undefined).subscribe({
      next: (blob) => saveBlob(blob, 'plantilla-equipos.csv'),
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'No se pudo descargar la plantilla.')),
    });
  }

  protected run(dryRun: boolean): void {
    const file = this.file();
    if (!file) return;
    this.busy.set(true);
    this.error.set(null);
    this.service.importCsv(file, dryRun).subscribe({
      next: (result) => {
        this.busy.set(false);
        this.preview.set(result);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err, 'No se pudo procesar el archivo.'));
      },
    });
  }
}
