import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable } from 'rxjs';
import { apiErrorMessage } from '../../../core/api/errors';
import { Personal } from '../../../core/api/models';
import { AuthService } from '../../../core/auth/auth.service';
import { PersonalService } from './personal.service';

type StaffRole = Personal['role'];

const ROLES: { value: StaffRole; label: string }[] = [
  { value: 'admin', label: 'Administrador' },
  { value: 'ventas', label: 'Ventas' },
  { value: 'operador', label: 'Operador' },
];

/** Alta, roles y bajas del personal de CHRISCO. Quien se da de alta crea su contraseña por correo. */
@Component({
  selector: 'app-personal-page',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1 class="text-lg font-black">Personal</h1>
    <p class="text-xs text-slate-500">
      Administrador: todo. Ventas: ve y cotiza. Operador: entrega y recibe equipos.
    </p>

    @if (error()) {
      <p role="alert" class="alert-error mt-3">{{ error() }}</p>
    }
    @if (aviso()) {
      <p role="status" class="alert-ok mt-3">{{ aviso() }}</p>
    }

    <div class="mt-3 overflow-x-auto rounded-xl border bg-white">
      <table class="w-full text-left text-xs">
        <thead class="bg-chrisco-charcoal text-[10px] font-bold text-white uppercase">
          <tr>
            <th class="p-3">Nombre</th>
            <th class="p-3">Rol</th>
            <th class="p-3">Estado</th>
            <th class="p-3"></th>
          </tr>
        </thead>
        <tbody class="divide-y">
          @for (p of people(); track p.id) {
            <tr [attr.data-persona]="p.email">
              <td class="p-3">
                <span class="font-semibold">{{ p.full_name }}</span
                ><br /><span class="text-slate-500">{{ p.email }}</span>
              </td>
              <td class="p-3">
                <select
                  class="input"
                  [attr.aria-label]="'Rol de ' + p.email"
                  [value]="p.role"
                  [disabled]="busy() || isMe(p)"
                  (change)="cambiarRol(p, $any($event.target).value)"
                >
                  @for (r of roles; track r.value) {
                    <option [value]="r.value" [selected]="r.value === p.role">{{ r.label }}</option>
                  }
                </select>
              </td>
              <td class="p-3">
                @if (!p.is_active) {
                  <span class="font-bold text-slate-500">De baja</span>
                } @else if (p.pendiente_invitacion) {
                  <span class="font-bold text-amber-700">Invitación pendiente</span>
                } @else {
                  <span class="font-bold text-emerald-700">Activo</span>
                }
              </td>
              <td class="p-3">
                <div class="flex flex-wrap gap-3">
                  @if (p.is_active && p.pendiente_invitacion) {
                    <button type="button" class="link" (click)="reenviar(p)">
                      Reenviar invitación
                    </button>
                  }
                  @if (!isMe(p)) {
                    <button
                      type="button"
                      class="link"
                      [class.text-rose-700]="p.is_active"
                      [disabled]="busy()"
                      (click)="alternarBaja(p)"
                    >
                      {{ p.is_active ? 'Dar de baja' : 'Reactivar' }}
                    </button>
                  }
                </div>
              </td>
            </tr>
          } @empty {
            <tr>
              <td colspan="4" class="p-6 text-center text-slate-500">Cargando…</td>
            </tr>
          }
        </tbody>
      </table>
    </div>

    <form [formGroup]="form" (ngSubmit)="crear()" class="card mt-4 space-y-3" novalidate>
      <h2 class="text-sm font-black">Dar de alta a una persona</h2>
      <div class="grid gap-3 sm:grid-cols-3">
        <div>
          <label for="per-nombre" class="label">Nombre completo</label>
          <input id="per-nombre" formControlName="full_name" class="input" />
        </div>
        <div>
          <label for="per-correo" class="label">Correo</label>
          <input id="per-correo" type="email" formControlName="email" class="input" />
        </div>
        <div>
          <label for="per-rol" class="label">Rol</label>
          <select id="per-rol" formControlName="role" class="input">
            @for (r of roles; track r.value) {
              <option [value]="r.value">{{ r.label }}</option>
            }
          </select>
        </div>
      </div>
      <button type="submit" class="btn-primary" [disabled]="form.invalid || busy()">
        Enviar invitación
      </button>
    </form>
  `,
})
export class PersonalPage implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly service = inject(PersonalService);
  private readonly auth = inject(AuthService);

  protected readonly roles = ROLES;
  protected readonly people = signal<Personal[]>([]);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly aviso = signal<string | null>(null);

  protected readonly form = this.fb.group({
    full_name: ['', [Validators.required, Validators.minLength(2)]],
    email: ['', [Validators.required, Validators.email]],
    role: ['operador' as StaffRole],
  });

  ngOnInit(): void {
    this.load();
  }

  protected isMe(p: Personal): boolean {
    return p.email === this.auth.user()?.email;
  }

  protected crear(): void {
    if (this.form.invalid) return;
    const v = this.form.getRawValue();
    this.run(
      this.service.create({ full_name: v.full_name.trim(), email: v.email.trim(), role: v.role }),
      'No se pudo dar de alta a la persona.',
      `Invitación enviada a ${v.email.trim()}.`,
      () => this.form.reset({ full_name: '', email: '', role: 'operador' }),
    );
  }

  protected cambiarRol(p: Personal, role: StaffRole): void {
    if (role === p.role) return;
    this.run(this.service.update(p.id, { role }), 'No se pudo cambiar el rol.', 'Rol actualizado.');
  }

  protected alternarBaja(p: Personal): void {
    this.run(
      this.service.update(p.id, { is_active: !p.is_active }),
      'No se pudo cambiar el estado.',
      p.is_active ? 'Persona dada de baja.' : 'Persona reactivada.',
    );
  }

  protected reenviar(p: Personal): void {
    this.run(
      this.service.resendInvitation(p.id),
      'No se pudo reenviar la invitación.',
      `Invitación reenviada a ${p.email}.`,
    );
  }

  private run(
    request: Observable<unknown>,
    failure: string,
    success: string,
    done?: () => void,
  ): void {
    this.busy.set(true);
    this.error.set(null);
    this.aviso.set(null);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.aviso.set(success);
        done?.();
        this.load();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(apiErrorMessage(err, failure));
        this.load(); // vuelve a mostrar el valor real (p. ej. el rol que no cambió)
      },
    });
  }

  private load(): void {
    this.service.list().subscribe({
      next: (people) => this.people.set(people),
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'No se pudo cargar el personal.')),
    });
  }
}
