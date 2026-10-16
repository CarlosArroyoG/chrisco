import {
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  inject,
  input,
  OnInit,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { catchError, concatMap, from, of, toArray } from 'rxjs';
import { apiErrorMessage } from '../../../core/api/errors';
import { Categoria, Equipo, EquipoInput } from '../../../core/api/models';
import { AuthService } from '../../../core/auth/auth.service';
import { CatalogoService, fotoUrl } from '../../../core/catalogo/catalogo.service';
import { FotoItem, FotosEquipo } from '../../../shared/fotos-equipo/fotos-equipo';
import {
  buildSpecGroup,
  SpecFields,
  SpecGroup,
  specValues,
} from '../../../shared/spec-fields/spec-fields';
import { StatusBadge } from '../../../shared/status-badge/status-badge';
import { EquipoMantenimiento } from '../mantenimiento/equipo-mantenimiento';
import { EquipoBloqueos } from './equipo-bloqueos';
import { EquiposService } from './equipos.service';

/** Exige al menos una tarifa (por hora o por día), igual que la API. */
function atLeastOneRate(group: AbstractControl): ValidationErrors | null {
  const { tarifa_hora, tarifa_dia } = group.value;
  return tarifa_hora || tarifa_dia ? null : { rate: true };
}

/** Alta y edición de un equipo, con sus especificaciones y fotos. Solo lectura para ventas. */
@Component({
  selector: 'app-equipo-form',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    SpecFields,
    StatusBadge,
    EquipoBloqueos,
    EquipoMantenimiento,
    FotosEquipo,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a routerLink="/admin/equipos" class="link text-xs">← Volver a equipos</a>
    <div class="mt-2 flex flex-wrap items-center gap-3">
      <h1 class="text-lg font-black">
        {{ id() ? (equipo()?.nombre ?? 'Equipo') : 'Nuevo equipo' }}
      </h1>
      @if (equipo(); as e) {
        <app-status-badge [status]="e.estado_actual" />
      }
    </div>

    @if (ready()) {
      <form [formGroup]="form" (ngSubmit)="save()" class="mt-3 space-y-4" novalidate>
        <section class="card space-y-3">
          <h2 class="text-sm font-black">Datos generales</h2>
          <div class="grid gap-3 sm:grid-cols-3">
            <div>
              <label for="codigo" class="label">Código *</label>
              <input id="codigo" formControlName="codigo" class="input uppercase" />
            </div>
            <div class="sm:col-span-2">
              <label for="categoria" class="label">Categoría *</label>
              <select id="categoria" formControlName="categoria_id" class="input">
                <option value="" disabled>Elige una categoría</option>
                @for (c of categorias(); track c.id) {
                  <option [value]="c.id">{{ c.nombre }}</option>
                }
              </select>
            </div>
          </div>
          <div>
            <label for="nombre" class="label">Nombre *</label>
            <input id="nombre" formControlName="nombre" class="input" />
          </div>
          <div class="grid gap-3 sm:grid-cols-4">
            <div>
              <label for="marca" class="label">Marca *</label>
              <input id="marca" formControlName="marca" class="input" />
            </div>
            <div>
              <label for="modelo" class="label">Modelo *</label>
              <input id="modelo" formControlName="modelo" class="input" />
            </div>
            <div>
              <label for="serie" class="label">Número de serie *</label>
              <input id="serie" formControlName="numero_serie" class="input" />
            </div>
            <div>
              <label for="anio" class="label">Año</label>
              <input id="anio" type="number" formControlName="anio" class="input" />
            </div>
          </div>
          <div class="grid gap-3 sm:grid-cols-3">
            <div>
              <label for="horometro" class="label">Horómetro (h)</label>
              <input
                id="horometro"
                type="number"
                step="0.1"
                formControlName="horometro"
                class="input"
              />
            </div>
            <div class="sm:col-span-2">
              <label for="patio" class="label">Patio *</label>
              <input id="patio" formControlName="patio" class="input" />
            </div>
          </div>
          @if (id()) {
            <div class="sm:w-1/3">
              <label for="status" class="label">Estado</label>
              <select id="status" formControlName="status" class="input">
                <option value="activo">Activo</option>
                <option value="mantenimiento">En mantenimiento</option>
                <option value="baja">Baja (no aparece en el catálogo)</option>
              </select>
            </div>
          }
        </section>

        <section class="card space-y-3">
          <h2 class="text-sm font-black">Tarifas y requisitos</h2>
          <div class="grid gap-3 sm:grid-cols-2">
            <div>
              <label for="tarifa_hora" class="label">Tarifa por hora (MXN)</label>
              <input
                id="tarifa_hora"
                type="number"
                step="0.01"
                formControlName="tarifa_hora"
                class="input"
              />
            </div>
            <div>
              <label for="tarifa_dia" class="label">Tarifa por día (MXN)</label>
              <input
                id="tarifa_dia"
                type="number"
                step="0.01"
                formControlName="tarifa_dia"
                class="input"
              />
            </div>
          </div>
          @if (form.errors?.['rate'] && form.touched) {
            <p class="alert-error">Captura la tarifa por hora, por día o ambas.</p>
          }
          <div class="flex flex-wrap gap-x-6 gap-y-2 text-sm font-semibold">
            <label class="flex items-center gap-2">
              <input type="checkbox" formControlName="requiere_lowboy" class="size-4" />
              Se transporta en lowboy
            </label>
            <label class="flex items-center gap-2">
              <input
                type="checkbox"
                formControlName="requiere_operador_certificado"
                class="size-4"
              />
              Requiere operador certificado
            </label>
          </div>
        </section>

        @if (fields().length) {
          <section class="card space-y-3">
            <h2 class="text-sm font-black">Especificaciones</h2>
            <app-spec-fields [fields]="fields()" [group]="specGroup()" />
          </section>
        }

        <section class="card">
          <label for="descripcion" class="label">Descripción para el cliente</label>
          <textarea
            id="descripcion"
            formControlName="descripcion"
            rows="4"
            maxlength="2000"
            placeholder="Para qué sirve, qué incluye, condiciones de uso…"
            class="input"
          ></textarea>
          <p class="mt-1 text-xs text-slate-500">
            Se muestra en el catálogo junto a las fotos y las especificaciones.
          </p>
        </section>

        <section class="card">
          <label for="notas" class="label">Notas internas (el cliente no las ve)</label>
          <textarea id="notas" formControlName="notas" rows="2" class="input"></textarea>
        </section>

        @if (!id()) {
          <app-fotos-equipo
            [fotos]="fotosPendientes()"
            [error]="photoError()"
            (add)="elegirFotos($event)"
            (remove)="quitarPendiente($event)"
          />
        }

        @if (error()) {
          <p role="alert" class="alert-error">{{ error() }}</p>
        }
        @if (saved()) {
          <p role="status" class="alert-ok">Cambios guardados.</p>
        }
        @if (canEdit()) {
          <button type="submit" [disabled]="saving()" class="btn-primary">
            {{ saving() ? 'Guardando…' : id() ? 'Guardar cambios' : 'Crear equipo' }}
          </button>
        } @else {
          <p class="text-xs text-slate-500">Solo un administrador puede modificar equipos.</p>
        }
      </form>
    } @else if (!error()) {
      <p class="mt-3 text-sm text-slate-500">Cargando…</p>
    }

    @if (equipo(); as e) {
      <app-fotos-equipo
        [fotos]="fotosGuardadas()"
        [canEdit]="canEdit()"
        [error]="photoError()"
        (add)="addFotos($event)"
        (remove)="removeFoto($event)"
      />

      <app-equipo-bloqueos [equipoId]="e.id" [canEdit]="canEdit()" (changed)="refreshSituacion()" />
      <app-equipo-mantenimiento [equipoId]="e.id" [canEdit]="canEdit()" />
    }
  `,
})
export class EquipoForm implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly service = inject(EquiposService);
  private readonly catalogo = inject(CatalogoService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  /** Id de la ruta `/admin/equipos/:id`; no existe en `/admin/equipos/nuevo`. */
  readonly id = input<string>();

  protected readonly fotoUrl = fotoUrl;
  protected readonly categorias = signal<Categoria[]>([]);
  protected readonly equipo = signal<Equipo | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly photoError = signal<string | null>(null);
  /** Fotos elegidas al crear un equipo: se suben cuando el equipo ya existe. */
  private readonly pendientes = signal<{ file: File; url: string }[]>([]);
  protected readonly fotosPendientes = computed<FotoItem[]>(() =>
    this.pendientes().map((p) => ({ key: p.url, url: p.url, thumb: p.url })),
  );
  protected readonly fotosGuardadas = computed<FotoItem[]>(() =>
    (this.equipo()?.fotos ?? []).map((f) => ({
      key: f.id,
      url: fotoUrl(f.id, 'full'),
      thumb: fotoUrl(f.id, 'thumb'),
    })),
  );
  protected readonly saving = signal(false);
  protected readonly saved = signal(false);
  protected readonly canEdit = computed(() => this.auth.user()?.role === 'admin');
  /** El formulario solo se muestra con los datos ya cargados: así una carga tardía no pisa lo que el usuario cambió. */
  protected readonly ready = computed(() => !this.id() || this.equipo() !== null);

  protected readonly form = this.fb.group(
    {
      codigo: ['', [Validators.required, Validators.pattern(/^[A-Za-z0-9][A-Za-z0-9-]{1,29}$/)]],
      categoria_id: ['', Validators.required],
      nombre: ['', [Validators.required, Validators.minLength(2)]],
      marca: ['', Validators.required],
      modelo: ['', Validators.required],
      numero_serie: ['', [Validators.required, Validators.minLength(2)]],
      anio: [null as number | null],
      horometro: [0],
      patio: ['Patio Toluca CHRISCO', [Validators.required, Validators.minLength(2)]],
      tarifa_hora: [null as number | null],
      tarifa_dia: [null as number | null],
      requiere_lowboy: [false],
      requiere_operador_certificado: [false],
      status: ['activo' as 'activo' | 'mantenimiento' | 'baja'],
      descripcion: [''],
      notas: [''],
    },
    { validators: atLeastOneRate },
  );

  private readonly categoriaId = signal('');
  protected readonly fields = computed(
    () => this.categorias().find((c) => c.id === this.categoriaId())?.spec_fields ?? [],
  );
  protected readonly specGroup = signal<SpecGroup>(buildSpecGroup([]));

  ngOnInit(): void {
    const aviso = history.state?.avisoFotos;
    if (typeof aviso === 'string') this.photoError.set(`Algunas fotos no se subieron: ${aviso}`);
    this.catalogo.categorias().subscribe({
      next: (categorias) => {
        this.categorias.set(categorias);
        this.load();
      },
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'No se pudieron cargar las categorías.')),
    });
    this.form.controls.categoria_id.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((value) => this.onCategoria(value));
  }

  private onCategoria(categoriaId: string, saved: Record<string, unknown> = {}): void {
    this.categoriaId.set(categoriaId);
    // Al cambiar de categoría se conservan los valores de las especificaciones que se llaman igual.
    const keep = { ...specValues(this.fields(), this.specGroup()), ...saved };
    this.specGroup.set(buildSpecGroup(this.fields(), keep));
    if (!this.canEdit()) this.specGroup().disable();
  }

  private load(): void {
    const id = this.id();
    if (!id) return;
    this.service.get(id).subscribe({
      next: (equipo) => {
        this.equipo.set(equipo);
        this.form.patchValue(
          { ...equipo, notas: equipo.notas ?? '', descripcion: equipo.descripcion ?? '' },
          { emitEvent: false },
        );
        this.onCategoria(equipo.categoria_id, equipo.specs);
        if (!this.canEdit()) this.form.disable();
      },
      error: (err: unknown) => this.error.set(apiErrorMessage(err, 'No se pudo cargar el equipo.')),
    });
  }

  private payload(): EquipoInput {
    const v = this.form.getRawValue();
    return {
      ...v,
      codigo: v.codigo.trim().toUpperCase(),
      anio: v.anio || null,
      horometro: v.horometro ?? 0,
      tarifa_hora: v.tarifa_hora || null,
      tarifa_dia: v.tarifa_dia || null,
      descripcion: v.descripcion.trim() || null,
      notas: v.notas.trim() || null,
      specs: specValues(this.fields(), this.specGroup()),
    };
  }

  protected save(): void {
    this.form.markAllAsTouched();
    this.specGroup().markAllAsTouched();
    if (this.form.invalid || this.specGroup().invalid) {
      this.error.set('Revisa los campos marcados como obligatorios.');
      return;
    }
    this.saving.set(true);
    this.saved.set(false);
    this.error.set(null);
    const id = this.id();
    const request = id
      ? this.service.update(id, this.payload())
      : this.service.create(this.payload());
    request.subscribe({
      next: (equipo) => {
        this.saving.set(false);
        if (id) {
          this.equipo.set(equipo);
          this.saved.set(true);
        } else {
          // Tras crear, se suben las fotos elegidas y se abre el equipo.
          this.subirPendientes(equipo.id);
        }
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.error.set(apiErrorMessage(err, 'No se pudo guardar el equipo.'));
      },
    });
  }

  /** Tras cambiar un bloqueo se consulta solo la situación, sin tocar lo que se esté editando. */
  protected refreshSituacion(): void {
    const id = this.id();
    if (!id) return;
    this.service.get(id).subscribe((actual) => {
      this.equipo.update((e) => (e ? { ...e, estado_actual: actual.estado_actual } : e));
    });
  }

  protected addFotos(files: File[]): void {
    const equipo = this.equipo();
    if (!equipo || !files.length) return;
    this.photoError.set(null);
    // Se suben una por una para respetar el máximo de fotos y reportar el error de cada una.
    const next = (index: number): void => {
      if (index >= files.length) return;
      this.service.addFoto(equipo.id, files[index]).subscribe({
        next: (foto) => {
          this.equipo.update((e) => (e ? { ...e, fotos: [...e.fotos, foto] } : e));
          next(index + 1);
        },
        error: (err: unknown) =>
          this.photoError.set(`${files[index].name}: ${apiErrorMessage(err, 'no se pudo subir')}`),
      });
    };
    next(0);
  }

  /** Alta: las fotos se previsualizan ya, pero se suben cuando el equipo se guarda. */
  protected elegirFotos(files: File[]): void {
    const room = 10 - this.pendientes().length;
    const chosen = files.slice(0, room).map((file) => ({ file, url: URL.createObjectURL(file) }));
    this.pendientes.update((actuales) => [...actuales, ...chosen]);
    this.photoError.set(
      files.length > room
        ? 'Cada equipo admite hasta 10 fotos: se agregaron solo las primeras.'
        : null,
    );
  }

  protected quitarPendiente(url: string): void {
    URL.revokeObjectURL(url);
    this.pendientes.update((actuales) => actuales.filter((p) => p.url !== url));
  }

  /** Sube las fotos elegidas al crear y abre el equipo; si alguna falla, avisa allá. */
  private subirPendientes(equipoId: string): void {
    const archivos = this.pendientes().map((p) => p.file);
    const fallas: string[] = [];
    from(archivos)
      .pipe(
        concatMap((file) =>
          this.service.addFoto(equipoId, file).pipe(
            catchError((err: unknown) => {
              fallas.push(`${file.name}: ${apiErrorMessage(err, 'no se pudo subir')}`);
              return of(null);
            }),
          ),
        ),
        toArray(),
      )
      .subscribe(() => {
        this.pendientes().forEach((p) => URL.revokeObjectURL(p.url));
        void this.router.navigate(['/admin/equipos', equipoId], {
          state: fallas.length ? { avisoFotos: fallas.join(' · ') } : {},
        });
      });
  }

  protected removeFoto(fotoId: string): void {
    const equipo = this.equipo();
    if (!equipo) return;
    this.service.removeFoto(equipo.id, fotoId).subscribe({
      next: () =>
        this.equipo.update((e) =>
          e ? { ...e, fotos: e.fotos.filter((f) => f.id !== fotoId) } : e,
        ),
      error: (err: unknown) =>
        this.photoError.set(apiErrorMessage(err, 'No se pudo quitar la foto.')),
    });
  }
}
