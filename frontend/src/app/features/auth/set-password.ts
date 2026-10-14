import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../core/api/errors';
import { AuthService } from '../../core/auth/auth.service';
import { AuthCard } from '../../shared/auth-card/auth-card';

const COPY = {
  invite: { title: 'Crea tu contraseña', subtitle: 'Te invitaron a CHRISCO Go' },
  reset: { title: 'Nueva contraseña', subtitle: 'Elige una contraseña nueva para tu cuenta' },
};

/** Sirve a `/aceptar-invitacion` y a `/recuperar-contrasena`: cambia el modo (route data) y el texto. */
@Component({
  selector: 'app-set-password',
  imports: [ReactiveFormsModule, RouterLink, AuthCard],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-auth-card [title]="copy().title" [subtitle]="copy().subtitle">
      @if (done()) {
        <p role="status" class="alert-ok">Contraseña guardada. Ya puedes iniciar sesión.</p>
        <a routerLink="/login" class="btn-primary mt-4 block text-center">Iniciar sesión</a>
      } @else {
        <form [formGroup]="form" (ngSubmit)="submit()" class="space-y-3" novalidate>
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
          @if (error()) {
            <p role="alert" class="alert-error">{{ error() }}</p>
          }
          <button type="submit" [disabled]="form.invalid || loading()" class="btn-primary w-full">
            {{ loading() ? 'Guardando…' : 'Guardar contraseña' }}
          </button>
        </form>
      }
    </app-auth-card>
  `,
})
export class SetPassword {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly auth = inject(AuthService);

  /** `token` viene del query param; `mode` de los datos de la ruta (withComponentInputBinding). */
  readonly token = input('');
  readonly mode = input<'invite' | 'reset'>('reset');
  protected readonly copy = computed(() => COPY[this.mode()]);

  protected readonly form = this.fb.group({
    password: ['', [Validators.required, Validators.minLength(10)]],
  });
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly done = signal(false);

  protected submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set(null);
    this.auth.setPassword(this.mode(), this.token(), this.form.getRawValue().password).subscribe({
      next: () => this.done.set(true),
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err, 'No se pudo guardar la contraseña.'));
      },
    });
  }
}
