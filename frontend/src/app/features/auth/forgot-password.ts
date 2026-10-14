import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../core/api/errors';
import { AuthService } from '../../core/auth/auth.service';
import { AuthCard } from '../../shared/auth-card/auth-card';

@Component({
  selector: 'app-forgot-password',
  imports: [ReactiveFormsModule, RouterLink, AuthCard],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-auth-card title="Recupera tu contraseña" subtitle="Te enviaremos un enlace por correo">
      @if (sent()) {
        <p role="status" class="alert-ok">
          Si el correo está registrado, recibirás un enlace para elegir una contraseña nueva.
        </p>
      } @else {
        <form [formGroup]="form" (ngSubmit)="submit()" class="space-y-3" novalidate>
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
          @if (error()) {
            <p role="alert" class="alert-error">{{ error() }}</p>
          }
          <button type="submit" [disabled]="form.invalid || loading()" class="btn-primary w-full">
            {{ loading() ? 'Enviando…' : 'Enviar enlace' }}
          </button>
        </form>
      }
      <a routerLink="/login" class="link mt-4 block text-center text-xs">Volver al inicio</a>
    </app-auth-card>
  `,
})
export class ForgotPassword {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly auth = inject(AuthService);

  protected readonly form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
  });
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly sent = signal(false);

  protected submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set(null);
    this.auth.forgotPassword(this.form.getRawValue().email).subscribe({
      next: () => this.sent.set(true),
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err, 'No se pudo enviar el enlace.'));
      },
    });
  }
}
