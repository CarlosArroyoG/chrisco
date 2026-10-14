import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'app-admin-home',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1 class="text-lg font-black">Panel de administración</h1>
    <p class="text-sm text-slate-500">
      Las rentas, equipos y cobranza llegan en las siguientes fases.
    </p>
  `,
})
export class AdminHome {}
