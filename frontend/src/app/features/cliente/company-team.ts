import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { apiErrorMessage } from '../../core/api/errors';
import { EmpresaDetail } from '../../core/api/models';
import { EmpresaService } from '../../core/empresa/empresa.service';

/** Usuarios de la empresa. El titular invita (hasta el máximo) y da de baja; los demás solo ven. */
@Component({
  selector: 'app-company-team',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card">
      <h2 class="text-sm font-black">
        Usuarios de tu empresa ({{ activeUsers().length }}/{{ empresa().max_users }})
      </h2>
      <ul class="mt-3 divide-y divide-slate-100 text-sm">
        @for (user of activeUsers(); track user.id) {
          <li class="flex items-center justify-between gap-3 py-2">
            <div class="min-w-0">
              <p class="truncate font-semibold">
                {{ user.full_name }}
                @if (user.is_company_owner) {
                  <span class="ml-1 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold"
                    >Titular</span
                  >
                }
                @if (!user.email_verified_at) {
                  <span
                    class="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800"
                  >
                    Invitación pendiente
                  </span>
                }
              </p>
              <p class="truncate text-xs text-slate-500">{{ user.email }}</p>
            </div>
            @if (isOwner() && !user.is_company_owner) {
              <button type="button" (click)="remove(user.id)" class="link text-xs text-rose-700">
                Dar de baja
              </button>
            }
          </li>
        }
      </ul>

      @if (isOwner()) {
        @if (activeUsers().length < empresa().max_users) {
          <form
            [formGroup]="form"
            (ngSubmit)="invite()"
            class="mt-4 space-y-3 border-t pt-4"
            novalidate
          >
            <h3 class="text-xs font-black text-slate-500 uppercase">Invitar a un compañero</h3>
            <div class="grid gap-3 sm:grid-cols-2">
              <div>
                <label for="inv-name" class="label">Nombre</label>
                <input id="inv-name" formControlName="full_name" class="input" />
              </div>
              <div>
                <label for="inv-email" class="label">Correo</label>
                <input id="inv-email" type="email" formControlName="email" class="input" />
              </div>
            </div>
            @if (error()) {
              <p role="alert" class="alert-error">{{ error() }}</p>
            }
            <button type="submit" [disabled]="form.invalid || loading()" class="btn-primary">
              {{ loading() ? 'Enviando…' : 'Enviar invitación' }}
            </button>
          </form>
        } @else {
          <p class="mt-4 text-xs text-slate-500">
            Llegaste al máximo de usuarios. Da de baja a alguien para invitar a otra persona.
          </p>
        }
      }
    </section>
  `,
})
export class CompanyTeam {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly empresas = inject(EmpresaService);

  readonly empresa = input.required<EmpresaDetail>();
  readonly isOwner = input.required<boolean>();
  readonly changed = output<void>();

  protected readonly activeUsers = computed(() => this.empresa().users.filter((u) => u.is_active));
  protected readonly form = this.fb.group({
    full_name: ['', [Validators.required, Validators.minLength(2)]],
    email: ['', [Validators.required, Validators.email]],
  });
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  protected invite(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set(null);
    const { email, full_name } = this.form.getRawValue();
    this.empresas.inviteUser(email, full_name).subscribe({
      next: () => {
        this.loading.set(false);
        this.form.reset();
        this.changed.emit();
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err, 'No se pudo enviar la invitación.'));
      },
    });
  }

  protected remove(userId: string): void {
    this.error.set(null);
    this.empresas.removeUser(userId).subscribe({
      next: () => this.changed.emit(),
      error: (err: unknown) => this.error.set(apiErrorMessage(err, 'No se pudo dar de baja.')),
    });
  }
}
