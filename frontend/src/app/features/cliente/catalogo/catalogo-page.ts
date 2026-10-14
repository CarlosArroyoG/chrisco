import { CurrencyPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { debounceTime, distinctUntilChanged } from 'rxjs';
import { apiErrorMessage } from '../../../core/api/errors';
import { Categoria, EquipoCatalogo } from '../../../core/api/models';
import { CatalogoService, fotoUrl } from '../../../core/catalogo/catalogo.service';

const PAGE_SIZE = 12;

/** Catálogo de maquinaria para clientes con empresa aprobada. */
@Component({
  selector: 'app-catalogo-page',
  imports: [CurrencyPipe, ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a routerLink="/cliente" class="link text-xs">← Mi empresa</a>
    <h1 class="mt-2 text-lg font-black">Catálogo de maquinaria ({{ total() }})</h1>

    <div class="mt-3 grid gap-2 sm:grid-cols-3">
      <input
        type="search"
        [formControl]="q"
        placeholder="Buscar equipo, marca o modelo…"
        aria-label="Buscar"
        class="input sm:col-span-2"
      />
      <select [formControl]="categoria" aria-label="Categoría" class="input">
        <option value="">Todas las categorías</option>
        @for (c of categorias(); track c.id) {
          <option [value]="c.id">{{ c.nombre }}</option>
        }
      </select>
    </div>

    @if (error()) {
      <p role="alert" class="alert-error mt-3">{{ error() }}</p>
    }

    <div class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      @for (e of items(); track e.id) {
        <a
          [routerLink]="['/cliente/catalogo', e.id]"
          class="card block overflow-hidden !p-0 transition hover:shadow-md"
        >
          @if (e.fotos.length) {
            <img
              [src]="fotoUrl(e.fotos[0].id, 'thumb')"
              [alt]="e.nombre"
              class="aspect-[4/3] w-full object-cover"
              loading="lazy"
            />
          } @else {
            <div
              class="flex aspect-[4/3] items-center justify-center bg-slate-100 text-xs text-slate-400"
            >
              Sin foto
            </div>
          }
          <div class="space-y-1 p-4">
            <p class="text-[10px] font-bold text-slate-500 uppercase">{{ e.categoria_nombre }}</p>
            <h2 class="font-black">{{ e.nombre }}</h2>
            <p class="text-xs text-slate-500">
              {{ e.marca }} {{ e.modelo }}
              @if (e.anio) {
                · {{ e.anio }}
              }
            </p>
            <p class="pt-1 text-sm font-black">
              @if (e.tarifa_hora) {
                {{ e.tarifa_hora | currency: 'MXN' : 'symbol-narrow' : '1.0-2' }}/h
              }
              @if (e.tarifa_hora && e.tarifa_dia) {
                ·
              }
              @if (e.tarifa_dia) {
                {{ e.tarifa_dia | currency: 'MXN' : 'symbol-narrow' : '1.0-2' }}/día
              }
            </p>
            @if (e.requiere_lowboy) {
              <p class="text-[11px] font-semibold text-amber-700">Se entrega en lowboy</p>
            }
          </div>
        </a>
      } @empty {
        <p class="col-span-full text-sm text-slate-500">
          {{ loaded() ? 'No encontramos equipos con esos filtros.' : 'Cargando…' }}
        </p>
      }
    </div>

    @if (pages() > 1) {
      <nav class="mt-4 flex items-center justify-between text-xs" aria-label="Paginación">
        <button
          type="button"
          class="btn-secondary"
          [disabled]="page() === 0"
          (click)="go(page() - 1)"
        >
          Anterior
        </button>
        <span>Página {{ page() + 1 }} de {{ pages() }}</span>
        <button
          type="button"
          class="btn-secondary"
          [disabled]="page() + 1 >= pages()"
          (click)="go(page() + 1)"
        >
          Siguiente
        </button>
      </nav>
    }
  `,
})
export class CatalogoPage implements OnInit {
  private readonly service = inject(CatalogoService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly fotoUrl = fotoUrl;
  protected readonly q = new FormControl('', { nonNullable: true });
  protected readonly categoria = new FormControl('', { nonNullable: true });
  protected readonly categorias = signal<Categoria[]>([]);
  protected readonly items = signal<EquipoCatalogo[]>([]);
  protected readonly total = signal(0);
  protected readonly page = signal(0);
  protected readonly loaded = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / PAGE_SIZE)));

  ngOnInit(): void {
    this.service.categorias().subscribe((categorias) => this.categorias.set(categorias));
    this.q.valueChanges
      .pipe(debounceTime(300), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.go(0));
    this.categoria.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.go(0));
    this.go(0);
  }

  protected go(page: number): void {
    this.page.set(page);
    this.loaded.set(false);
    this.error.set(null);
    this.service
      .list({
        q: this.q.value.trim(),
        categoria_id: this.categoria.value,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      })
      .subscribe({
        next: (result) => {
          this.items.set(result.items);
          this.total.set(result.total);
          this.loaded.set(true);
        },
        error: (err: unknown) => {
          this.loaded.set(true);
          this.error.set(apiErrorMessage(err, 'No se pudo cargar el catálogo.'));
        },
      });
  }
}
