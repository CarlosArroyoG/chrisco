import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'app-cliente-home',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1 class="text-lg font-black">Catálogo de maquinaria</h1>
    <p class="text-sm text-slate-500">
      El catálogo y las solicitudes de renta llegan en las siguientes fases.
    </p>
  `,
})
export class ClienteHome {}
