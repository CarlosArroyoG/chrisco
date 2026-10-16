import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  OnInit,
  signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../core/api/errors';
import { openBlob } from '../../core/api/download';
import { EmpresaDetail } from '../../core/api/models';
import { AuthService } from '../../core/auth/auth.service';
import { StatusBadge } from '../../shared/status-badge/status-badge';
import { AdminEmpresasService } from './admin-empresas.service';

/** Detalle de una empresa: datos, constancia y la decisión (aprobar o rechazar, solo admin). */
@Component({
  selector: 'app-empresa-review',
  imports: [DatePipe, ReactiveFormsModule, RouterLink, StatusBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a routerLink="/admin/empresas" class="link text-xs">← Volver a empresas</a>
    @if (error()) {
      <p role="alert" class="alert-error mt-3">{{ error() }}</p>
    }
    @if (empresa(); as e) {
      <section class="card mt-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h1 class="text-lg font-black">{{ e.razon_social }}</h1>
          <app-status-badge [status]="e.status" />
        </div>
        <dl class="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <div>
            <dt class="label">RFC</dt>
            <dd class="font-mono">{{ e.rfc }}</dd>
          </div>
          <div>
            <dt class="label">Página web</dt>
            <dd>
              <a [href]="e.sitio_web" target="_blank" rel="noopener noreferrer" class="link">{{
                e.sitio_web
              }}</a>
            </dd>
          </div>
          <div>
            <dt class="label">Registro</dt>
            <dd>{{ e.created_at | date: 'dd/MM/yyyy HH:mm' }}</dd>
          </div>
          @if (e.reviewed_at) {
            <div>
              <dt class="label">Revisada</dt>
              <dd>{{ e.reviewed_at | date: 'dd/MM/yyyy HH:mm' }}</dd>
            </div>
          }
        </dl>
        @if (e.motivo_rechazo) {
          <p class="alert-error mt-3">Motivo del rechazo: {{ e.motivo_rechazo }}</p>
        }
        <button type="button" (click)="openConstancia()" class="btn-secondary mt-4">
          Ver constancia de situación fiscal (PDF)
        </button>
      </section>

      <section class="card mt-4">
        <h2 class="text-sm font-black">Usuarios</h2>
        <ul class="mt-2 divide-y text-sm">
          @for (u of e.users; track u.id) {
            <li class="py-2">
              <span class="font-semibold">{{ u.full_name }}</span>
              @if (u.is_company_owner) {
                <span class="ml-1 text-[10px] font-bold">(titular)</span>
              }
              <span class="block text-xs text-slate-500">
                {{ u.email }} ·
                {{ u.email_verified_at ? 'correo confirmado' : 'correo sin confirmar' }}
                @if (!u.is_active) {
                  · baja
                }
              </span>
            </li>
          }
        </ul>
      </section>

      @if (e.status === 'pendiente') {
        <section class="card mt-4">
          <h2 class="text-sm font-black">Decisión</h2>
          @if (canDecide()) {
            <div class="mt-3 flex flex-wrap gap-2">
              <button type="button" (click)="approve()" [disabled]="busy()" class="btn-primary">
                Aprobar empresa
              </button>
            </div>
            <form [formGroup]="form" (ngSubmit)="reject()" class="mt-4 space-y-2" novalidate>
              <label for="motivo" class="label">Motivo del rechazo (se envía al titular)</label>
              <textarea id="motivo" formControlName="motivo" rows="3" class="input"></textarea>
              <button type="submit" [disabled]="form.invalid || busy()" class="btn-danger">
                Rechazar
              </button>
            </form>
          } @else {
            <p class="mt-2 text-xs text-slate-500">
              Solo un administrador puede aprobar o rechazar.
            </p>
          }
        </section>
      }
    }
  `,
})
export class EmpresaReview implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly service = inject(AdminEmpresasService);
  private readonly auth = inject(AuthService);

  /** Id de la ruta `/admin/empresas/:id` (withComponentInputBinding). */
  readonly id = input.required<string>();

  protected readonly empresa = signal<EmpresaDetail | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly busy = signal(false);
  protected readonly canDecide = computed(() => this.auth.user()?.role === 'admin');
  protected readonly form = this.fb.group({
    motivo: ['', [Validators.required, Validators.minLength(5), Validators.maxLength(500)]],
  });

  ngOnInit(): void {
    this.load();
  }

  protected openConstancia(): void {
    this.service.constancia(this.id()).subscribe({
      next: openBlob,
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'No se pudo abrir la constancia.')),
    });
  }

  protected approve(): void {
    this.decide(this.service.approve(this.id()));
  }

  protected reject(): void {
    if (this.form.valid)
      this.decide(this.service.reject(this.id(), this.form.getRawValue().motivo));
  }

  private decide(request: ReturnType<AdminEmpresasService['approve']>): void {
    this.busy.set(true);
    this.error.set(null);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.load();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err, 'No se pudo guardar la decisión.'));
      },
    });
  }

  private load(): void {
    this.service.get(this.id()).subscribe({
      next: (empresa) => this.empresa.set(empresa),
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'No se pudo cargar la empresa.')),
    });
  }
}
