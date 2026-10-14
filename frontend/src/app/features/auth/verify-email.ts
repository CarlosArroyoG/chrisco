import { ChangeDetectionStrategy, Component, inject, input, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../core/api/errors';
import { AuthService } from '../../core/auth/auth.service';
import { AuthCard } from '../../shared/auth-card/auth-card';

/** Destino del enlace de confirmación de correo (`/verificar-correo?token=...`). */
@Component({
  selector: 'app-verify-email',
  imports: [RouterLink, AuthCard],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-auth-card title="Confirmación de correo">
      @switch (state()) {
        @case ('loading') {
          <p class="text-center text-sm text-slate-500">Confirmando tu correo…</p>
        }
        @case ('ok') {
          <p role="status" class="alert-ok">¡Listo! Tu correo quedó confirmado.</p>
          <a routerLink="/login" class="btn-primary mt-4 block text-center">Iniciar sesión</a>
        }
        @default {
          <p role="alert" class="alert-error">{{ error() }}</p>
          <a routerLink="/login" class="link mt-4 block text-center text-xs">Volver al inicio</a>
        }
      }
    </app-auth-card>
  `,
})
export class VerifyEmail implements OnInit {
  private readonly auth = inject(AuthService);
  /** Viene del query param `token` (withComponentInputBinding). */
  readonly token = input('');

  protected readonly state = signal<'loading' | 'ok' | 'error'>('loading');
  protected readonly error = signal('');

  ngOnInit(): void {
    this.auth.verifyEmail(this.token()).subscribe({
      next: () => this.state.set('ok'),
      error: (err: unknown) => {
        this.error.set(apiErrorMessage(err, 'No se pudo confirmar tu correo.'));
        this.state.set('error');
      },
    });
  }
}
