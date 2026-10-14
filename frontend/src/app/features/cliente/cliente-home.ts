import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { apiErrorMessage } from '../../core/api/errors';
import { EmpresaDetail } from '../../core/api/models';
import { AuthService } from '../../core/auth/auth.service';
import { EmpresaService } from '../../core/empresa/empresa.service';
import { StatusBadge } from '../../shared/status-badge/status-badge';
import { CompanyTeam } from './company-team';
import { ResubmitForm } from './resubmit-form';

/** Inicio del cliente: estado de la verificación de su empresa y su equipo de usuarios. */
@Component({
  selector: 'app-cliente-home',
  imports: [RouterLink, StatusBadge, CompanyTeam, ResubmitForm],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (error()) {
      <p role="alert" class="alert-error">{{ error() }}</p>
    }
    @if (empresa(); as e) {
      <div class="space-y-4">
        <section class="card">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h1 class="text-lg font-black">{{ e.razon_social }}</h1>
              <p class="text-xs text-slate-500">RFC {{ e.rfc }} · {{ e.sitio_web }}</p>
            </div>
            <app-status-badge [status]="e.status" />
          </div>

          @switch (e.status) {
            @case ('pendiente') {
              <p class="mt-3 text-sm text-slate-600">
                Estamos revisando los datos y la constancia de tu empresa. Te avisaremos por correo
                cuando termine la revisión.
              </p>
            }
            @case ('rechazada') {
              <p role="alert" class="alert-error mt-3">Motivo: {{ e.motivo_rechazo }}</p>
              @if (isOwner()) {
                <app-resubmit-form [empresa]="e" (resubmitted)="empresa.set($event)" />
              } @else {
                <p class="mt-2 text-xs text-slate-500">
                  El titular de la empresa debe corregir los datos y volver a enviarlos.
                </p>
              }
            }
            @case ('aprobada') {
              <p class="mt-3 text-sm text-slate-600">
                Tu empresa está aprobada. Ya puedes consultar el catálogo de maquinaria.
              </p>
              <div class="mt-3 flex flex-wrap gap-2">
                <a routerLink="/cliente/catalogo" class="btn-primary">Ver catálogo de maquinaria</a>
                <a routerLink="/cliente/rentas" class="btn-secondary">Mis rentas</a>
              </div>
            }
          }
        </section>

        @if (e.status === 'aprobada') {
          <app-company-team [empresa]="e" [isOwner]="isOwner()" (changed)="load()" />
        }
      </div>
    } @else if (!error()) {
      <p class="text-sm text-slate-500">Cargando…</p>
    }
  `,
})
export class ClienteHome implements OnInit {
  private readonly empresas = inject(EmpresaService);
  private readonly auth = inject(AuthService);

  protected readonly empresa = signal<EmpresaDetail | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly isOwner = computed(() => {
    const me = this.auth.user();
    return !!this.empresa()?.users.find((u) => u.id === me?.id)?.is_company_owner;
  });

  ngOnInit(): void {
    this.load();
  }

  protected load(): void {
    this.empresas.mine().subscribe({
      next: (empresa) => this.empresa.set(empresa),
      error: (err: unknown) =>
        this.error.set(apiErrorMessage(err, 'No se pudo cargar la información de tu empresa.')),
    });
  }
}
