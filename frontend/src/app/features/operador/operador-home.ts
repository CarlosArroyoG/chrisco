import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'app-operador-home',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1 class="text-lg font-black">Modo operador</h1>
    <p class="text-sm text-slate-500">
      El check-in y check-out con horómetro llegan en una fase posterior.
    </p>
  `,
})
export class OperadorHome {}
