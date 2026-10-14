import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../core/api/errors';
import { EmpresaService } from '../../core/empresa/empresa.service';
import { AuthCard } from '../../shared/auth-card/auth-card';

/** Registro público de una empresa cliente y de su titular. */
@Component({
  selector: 'app-register',
  imports: [ReactiveFormsModule, RouterLink, AuthCard],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-auth-card
      title="Registra tu empresa"
      subtitle="Revisamos cada empresa antes de habilitar la renta de equipo"
      [wide]="true"
    >
      @if (done()) {
        <p role="status" class="alert-ok">{{ done() }}</p>
        <a routerLink="/login" class="btn-primary mt-4 block text-center">Ir a iniciar sesión</a>
      } @else {
        <form [formGroup]="form" (ngSubmit)="submit()" class="space-y-3" novalidate>
          <fieldset class="space-y-3">
            <legend class="text-xs font-black text-slate-500 uppercase">Datos de la empresa</legend>
            <div>
              <label for="razon_social" class="label">Razón social</label>
              <input id="razon_social" formControlName="razon_social" class="input" />
            </div>
            <div class="grid gap-3 sm:grid-cols-2">
              <div>
                <label for="rfc" class="label">RFC</label>
                <input
                  id="rfc"
                  formControlName="rfc"
                  maxlength="14"
                  autocapitalize="characters"
                  class="input uppercase"
                />
              </div>
              <div>
                <label for="sitio_web" class="label">Página web</label>
                <input
                  id="sitio_web"
                  formControlName="sitio_web"
                  placeholder="empresa.com"
                  class="input"
                />
              </div>
            </div>
            <div>
              <label for="constancia" class="label">Constancia de situación fiscal (PDF)</label>
              <input
                id="constancia"
                type="file"
                accept="application/pdf"
                (change)="onFile($event)"
                class="w-full text-xs"
              />
              <p class="mt-1 text-[11px] text-slate-500">
                Máximo 5 MB. Solo la ve el personal de CHRISCO para verificar a tu empresa.
              </p>
            </div>
          </fieldset>

          <fieldset class="space-y-3">
            <legend class="pt-2 text-xs font-black text-slate-500 uppercase">
              Titular de la cuenta
            </legend>
            <div>
              <label for="full_name" class="label">Nombre</label>
              <input id="full_name" formControlName="full_name" autocomplete="name" class="input" />
            </div>
            <div>
              <label for="email" class="label">Correo</label>
              <input
                id="email"
                type="email"
                formControlName="email"
                autocomplete="email"
                class="input"
              />
            </div>
            <div>
              <label for="password" class="label">Contraseña (mínimo 10 caracteres)</label>
              <input
                id="password"
                type="password"
                formControlName="password"
                autocomplete="new-password"
                class="input"
              />
            </div>
          </fieldset>

          @if (error()) {
            <p role="alert" class="alert-error">{{ error() }}</p>
          }
          <button
            type="submit"
            [disabled]="form.invalid || !constancia() || loading()"
            class="btn-primary w-full"
          >
            {{ loading() ? 'Enviando…' : 'Registrar empresa' }}
          </button>
          <p class="text-center text-xs">
            ¿Ya tienes cuenta? <a routerLink="/login" class="link">Inicia sesión</a>
          </p>
        </form>
      }
    </app-auth-card>
  `,
})
export class Register {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly empresas = inject(EmpresaService);

  protected readonly form = this.fb.group({
    razon_social: ['', [Validators.required, Validators.minLength(2)]],
    rfc: ['', [Validators.required, Validators.minLength(12)]],
    sitio_web: ['', [Validators.required, Validators.minLength(3)]],
    full_name: ['', [Validators.required, Validators.minLength(2)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(10)]],
  });
  protected readonly constancia = signal<File | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly done = signal<string | null>(null);

  protected onFile(event: Event): void {
    this.constancia.set((event.target as HTMLInputElement).files?.[0] ?? null);
  }

  protected submit(): void {
    const file = this.constancia();
    if (this.form.invalid || !file) return;
    this.loading.set(true);
    this.error.set(null);
    this.empresas.register(this.form.getRawValue(), file).subscribe({
      next: (res) => this.done.set(res.detail),
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err, 'No se pudo completar el registro.'));
      },
    });
  }
}
