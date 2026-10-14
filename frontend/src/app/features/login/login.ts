import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../core/api/errors';
import { HOME_BY_ROLE } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { AuthCard } from '../../shared/auth-card/auth-card';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, RouterLink, AuthCard],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-auth-card title="Acceso a la plataforma" subtitle="Ingresa con tu cuenta autorizada">
      <form [formGroup]="form" (ngSubmit)="submit()" class="space-y-3" novalidate>
        <div>
          <label for="email" class="label">Correo</label>
          <input
            id="email"
            type="email"
            formControlName="email"
            autocomplete="username"
            class="input"
          />
        </div>
        <div>
          <label for="password" class="label">Contraseña</label>
          <input
            id="password"
            type="password"
            formControlName="password"
            autocomplete="current-password"
            class="input"
          />
        </div>

        @if (error()) {
          <p role="alert" class="alert-error">{{ error() }}</p>
        }
        @if (unverified()) {
          <button type="button" (click)="resend()" class="link text-xs">
            Reenviar el correo de confirmación
          </button>
        }
        @if (notice()) {
          <p role="status" class="alert-ok">{{ notice() }}</p>
        }

        <button type="submit" [disabled]="form.invalid || loading()" class="btn-primary w-full">
          {{ loading() ? 'Entrando…' : 'Iniciar sesión' }}
        </button>
      </form>

      <div class="mt-4 flex justify-between text-xs">
        <a routerLink="/olvide-contrasena" class="link">¿Olvidaste tu contraseña?</a>
        <a routerLink="/registro" class="link">Registrar mi empresa</a>
      </div>
    </app-auth-card>
  `,
})
export class Login {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly unverified = signal(false);

  protected submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set(null);
    this.notice.set(null);
    this.unverified.set(false);
    const { email, password } = this.form.getRawValue();
    this.auth.login(email, password).subscribe({
      next: (user) => void this.router.navigate([HOME_BY_ROLE[user.role]]),
      error: (err: unknown) => {
        this.loading.set(false);
        this.unverified.set(err instanceof HttpErrorResponse && err.status === 403);
        this.error.set(apiErrorMessage(err, 'No se pudo iniciar sesión. Inténtalo de nuevo.'));
      },
    });
  }

  protected resend(): void {
    this.auth.resendVerification(this.form.getRawValue().email).subscribe({
      next: () => {
        this.error.set(null);
        this.unverified.set(false);
        this.notice.set('Si tu correo está pendiente de confirmar, te enviamos un nuevo enlace.');
      },
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'No se pudo reenviar el correo.')),
    });
  }
}
