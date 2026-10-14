import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { FormArray, FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { apiErrorMessage } from '../../../core/api/errors';
import { CategoriaAdmin, CategoriaIn, SpecField, SpecFieldType } from '../../../core/api/models';
import { AuthService } from '../../../core/auth/auth.service';
import { CategoriasService } from './categorias.service';

const TYPE_LABEL: Record<SpecFieldType, string> = {
  text: 'Texto',
  number: 'Número',
  boolean: 'Sí / No',
  select: 'Opciones',
};

/** Clave técnica a partir de la etiqueta: «Peso máximo» → «peso_maximo». */
export function slugify(label: string): string {
  const slug = label
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40);
  return /^[a-z]/.test(slug) ? slug : slug ? `c_${slug}`.slice(0, 40) : '';
}

/** Gestión de categorías de maquinaria y de las especificaciones que se capturan por equipo. */
@Component({
  selector: 'app-categorias-page',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1 class="text-lg font-black">Categorías de maquinaria</h1>
    <p class="text-xs text-slate-500">
      Cada categoría define qué especificaciones se capturan en sus equipos (peso, motor,
      capacidad…). Cambiarlas no modifica los equipos ya guardados.
    </p>

    @if (error()) {
      <p role="alert" class="alert-error mt-3">{{ error() }}</p>
    }

    @if (isAdmin()) {
      <section class="card mt-3">
        <h2 class="text-sm font-black">{{ editing() ? 'Editar categoría' : 'Nueva categoría' }}</h2>
        <form [formGroup]="form" (ngSubmit)="save()" class="mt-3 space-y-3" novalidate>
          <div class="sm:w-1/2">
            <label for="cat-nombre" class="label">Nombre *</label>
            <input id="cat-nombre" formControlName="nombre" class="input" />
          </div>

          <div class="space-y-2" formArrayName="spec_fields">
            <h3 class="text-xs font-black text-slate-500 uppercase">Especificaciones</h3>
            @for (row of specRows.controls; track row; let i = $index) {
              <div
                [formGroupName]="i"
                class="grid items-end gap-2 rounded-lg border p-2 sm:grid-cols-12"
              >
                <div class="sm:col-span-3">
                  <label [for]="'f-label-' + i" class="label">Etiqueta</label>
                  <input
                    [id]="'f-label-' + i"
                    formControlName="label"
                    placeholder="Peso máximo"
                    class="input"
                  />
                </div>
                <div class="sm:col-span-2">
                  <label [for]="'f-key-' + i" class="label">Clave</label>
                  <input [id]="'f-key-' + i" formControlName="key" class="input font-mono" />
                </div>
                <div class="sm:col-span-2">
                  <label [for]="'f-type-' + i" class="label">Tipo</label>
                  <select [id]="'f-type-' + i" formControlName="type" class="input">
                    @for (t of types; track t) {
                      <option [value]="t">{{ typeLabel[t] }}</option>
                    }
                  </select>
                </div>
                <div class="sm:col-span-1">
                  <label [for]="'f-unit-' + i" class="label">Unidad</label>
                  <input
                    [id]="'f-unit-' + i"
                    formControlName="unit"
                    placeholder="kg"
                    class="input"
                  />
                </div>
                <div class="sm:col-span-3">
                  @if (row.value.type === 'select') {
                    <label [for]="'f-opts-' + i" class="label">Opciones (separadas por coma)</label>
                    <input
                      [id]="'f-opts-' + i"
                      formControlName="options"
                      placeholder="Diésel, Gasolina"
                      class="input"
                    />
                  } @else {
                    <label class="flex items-center gap-2 pb-2 text-xs font-bold">
                      <input type="checkbox" formControlName="required" class="size-4" />
                      Obligatoria
                    </label>
                  }
                </div>
                <div class="sm:col-span-1 sm:text-right">
                  <button type="button" class="link text-xs text-rose-700" (click)="removeRow(i)">
                    Quitar
                  </button>
                </div>
              </div>
            }
            <button type="button" class="btn-secondary" (click)="addRow()">
              + Agregar especificación
            </button>
          </div>

          <div class="flex gap-2">
            <button type="submit" class="btn-primary" [disabled]="saving()">
              {{ saving() ? 'Guardando…' : editing() ? 'Guardar cambios' : 'Crear categoría' }}
            </button>
            @if (editing()) {
              <button type="button" class="btn-secondary" (click)="reset()">Cancelar</button>
            }
          </div>
        </form>
      </section>
    }

    <div class="mt-4 space-y-2">
      @for (c of categorias(); track c.id) {
        <section class="card flex flex-wrap items-center justify-between gap-2 !p-4">
          <div>
            <h2 class="text-sm font-black">{{ c.nombre }}</h2>
            <p class="text-xs text-slate-500">
              {{ c.equipos_count }} equipo(s) · {{ c.spec_fields.length }} especificación(es)
              @if (c.spec_fields.length) {
                : {{ specNames(c) }}
              }
            </p>
          </div>
          @if (isAdmin()) {
            <div class="flex items-center gap-3 text-xs">
              <button type="button" class="link" (click)="edit(c)">Editar</button>
              @if (confirmDelete() === c.id) {
                <span>¿Eliminar?</span>
                <button type="button" class="link text-rose-700" (click)="remove(c)">Sí</button>
                <button type="button" class="link" (click)="confirmDelete.set(null)">No</button>
              } @else {
                <button type="button" class="link text-rose-700" (click)="confirmDelete.set(c.id)">
                  Eliminar
                </button>
              }
            </div>
          }
        </section>
      } @empty {
        <p class="text-sm text-slate-500">
          {{ loaded() ? 'Aún no hay categorías.' : 'Cargando…' }}
        </p>
      }
    </div>
  `,
})
export class CategoriasPage implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly service = inject(CategoriasService);
  private readonly auth = inject(AuthService);

  protected readonly types: SpecFieldType[] = ['text', 'number', 'boolean', 'select'];
  protected readonly typeLabel = TYPE_LABEL;
  protected readonly categorias = signal<CategoriaAdmin[]>([]);
  protected readonly editing = signal<string | null>(null);
  protected readonly confirmDelete = signal<string | null>(null);
  protected readonly saving = signal(false);
  protected readonly loaded = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly isAdmin = computed(() => this.auth.user()?.role === 'admin');

  protected readonly specRows = new FormArray<FormGroup>([]);
  protected readonly form = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(2)]],
    spec_fields: this.specRows,
  });

  ngOnInit(): void {
    this.load();
  }

  /** `existing` marca filas ya guardadas: su clave no se puede cambiar sin huérfanar datos. */
  private newRow(field?: SpecField): FormGroup {
    const row = this.fb.group({
      label: [field?.label ?? '', Validators.required],
      key: [
        { value: field?.key ?? '', disabled: !!field },
        [Validators.required, Validators.pattern(/^[a-z][a-z0-9_]{0,39}$/)],
      ],
      type: [field?.type ?? ('text' as SpecFieldType)],
      unit: [field?.unit ?? ''],
      options: [field?.options?.join(', ') ?? ''],
      required: [field?.required ?? false],
    });
    if (!field) {
      // La clave se sugiere a partir de la etiqueta mientras nadie la haya tocado.
      row.get('label')?.valueChanges.subscribe((label: string) => {
        const key = row.get('key');
        if (key?.pristine) key.setValue(slugify(label), { emitEvent: false });
      });
    }
    return row;
  }

  protected addRow(): void {
    this.specRows.push(this.newRow());
  }

  protected removeRow(index: number): void {
    this.specRows.removeAt(index);
  }

  protected specNames(c: CategoriaAdmin): string {
    return c.spec_fields.map((f) => f.label).join(', ');
  }

  protected edit(c: CategoriaAdmin): void {
    this.editing.set(c.id);
    this.error.set(null);
    this.form.controls.nombre.setValue(c.nombre);
    this.specRows.clear();
    c.spec_fields.forEach((f) => this.specRows.push(this.newRow(f)));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  protected reset(): void {
    this.editing.set(null);
    this.form.reset({ nombre: '' });
    this.specRows.clear();
  }

  private payload(): CategoriaIn {
    const rows = this.specRows.getRawValue() as {
      label: string;
      key: string;
      type: SpecFieldType;
      unit: string;
      options: string;
      required: boolean;
    }[];
    return {
      nombre: this.form.controls.nombre.value.trim(),
      spec_fields: rows.map((r) => ({
        key: r.key,
        label: r.label.trim(),
        type: r.type,
        unit: r.unit.trim() || null,
        options:
          r.type === 'select'
            ? r.options
                .split(',')
                .map((o) => o.trim())
                .filter(Boolean)
            : [],
        required: r.type === 'boolean' ? false : r.required,
      })),
    };
  }

  protected save(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid) {
      this.error.set('Revisa el nombre y las especificaciones: todas necesitan etiqueta y clave.');
      return;
    }
    this.saving.set(true);
    this.error.set(null);
    const id = this.editing();
    const request = id
      ? this.service.update(id, this.payload())
      : this.service.create(this.payload());
    request.subscribe({
      next: () => {
        this.saving.set(false);
        this.reset();
        this.load();
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.error.set(apiErrorMessage(err, 'No se pudo guardar la categoría.'));
      },
    });
  }

  protected remove(c: CategoriaAdmin): void {
    this.confirmDelete.set(null);
    this.service.remove(c.id).subscribe({
      next: () => this.load(),
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'No se pudo eliminar la categoría.')),
    });
  }

  private load(): void {
    this.service.list().subscribe({
      next: (categorias) => {
        this.categorias.set(categorias);
        this.loaded.set(true);
      },
      error: (err: unknown) => {
        this.loaded.set(true);
        this.error.set(apiErrorMessage(err, 'No se pudieron cargar las categorías.'));
      },
    });
  }
}
