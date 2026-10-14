import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { HOME_BY_ROLE } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { Logo } from '../../shared/logo/logo';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule, Logo],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="bg-chrisco-dark fixed inset-0 flex items-center justify-center p-4">
      <section class="w-full max-w-sm rounded-2xl bg-white p-6 shadow-2xl">
        <div class="mb-4 flex justify-center"><app-logo class="h-24" /></div>
        <h1 class="text-center text-lg font-black">Acceso a la plataforma</h1>
        <p class="mb-5 text-center text-xs text-slate-500">Ingresa con tu cuenta autorizada</p>

        <form [formGroup]="form" (ngSubmit)="submit()" class="space-y-3 text-xs" novalidate>
          <div>
            <label for="email" class="mb-1 block font-bold text-slate-700">Correo</label>
            <input
              id="email"
              type="email"
              formControlName="email"
              autocomplete="username"
              class="focus:ring-chrisco-orange w-full rounded-lg border border-slate-300 p-2.5 outline-none focus:ring-2"
            />
          </div>
          <div>
            <label for="password" class="mb-1 block font-bold text-slate-700">Contraseña</label>
            <input
              id="password"
              type="password"
              formControlName="password"
              autocomplete="current-password"
              class="focus:ring-chrisco-orange w-full rounded-lg border border-slate-300 p-2.5 outline-none focus:ring-2"
            />
          </div>

          @if (error()) {
            <p role="alert" class="rounded-lg bg-rose-50 p-2 font-semibold text-rose-700">
              {{ error() }}
            </p>
          }

          <button
            type="submit"
            [disabled]="form.invalid || loading()"
            class="bg-chrisco-orange hover:bg-chrisco-orange-dark mt-2 w-full rounded-xl py-3 font-bold text-white shadow-md transition disabled:opacity-50"
          >
            {{ loading() ? 'Entrando…' : 'Iniciar sesión' }}
          </button>
        </form>
      </section>
    </main>
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

  protected submit(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set(null);
    const { email, password } = this.form.getRawValue();
    this.auth.login(email, password).subscribe({
      next: (user) => void this.router.navigate([HOME_BY_ROLE[user.role]]),
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(errorMessage(err));
      },
    });
  }
}

function errorMessage(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    if (err.status === 401) return 'Correo o contraseña incorrectos';
    if (err.status === 429) return 'Demasiados intentos. Espera un minuto e inténtalo de nuevo';
  }
  return 'No se pudo iniciar sesión. Revisa tu conexión e inténtalo de nuevo';
}
