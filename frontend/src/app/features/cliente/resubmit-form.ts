import {
  ChangeDetectionStrategy,
  Component,
  inject,
  input,
  OnInit,
  output,
  signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { apiErrorMessage } from '../../core/api/errors';
import { EmpresaDetail } from '../../core/api/models';
import { EmpresaService } from '../../core/empresa/empresa.service';

/** Tras un rechazo: el titular corrige los datos y vuelve a mandar la empresa a revisión. */
@Component({
  selector: 'app-resubmit-form',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <form [formGroup]="form" (ngSubmit)="submit()" class="mt-4 space-y-3" novalidate>
      <h3 class="text-sm font-black">Corrige tus datos y vuelve a enviarlos</h3>
      <div>
        <label for="rs-razon" class="label">Razón social</label>
        <input id="rs-razon" formControlName="razon_social" class="input" />
      </div>
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label for="rs-rfc" class="label">RFC</label>
          <input id="rs-rfc" formControlName="rfc" maxlength="14" class="input uppercase" />
        </div>
        <div>
          <label for="rs-web" class="label">Página web</label>
          <input id="rs-web" formControlName="sitio_web" class="input" />
        </div>
      </div>
      <div>
        <label for="rs-file" class="label">Nueva constancia de situación fiscal (PDF)</label>
        <input
          id="rs-file"
          type="file"
          accept="application/pdf"
          (change)="onFile($event)"
          class="w-full text-xs"
        />
      </div>
      @if (error()) {
        <p role="alert" class="alert-error">{{ error() }}</p>
      }
      <button type="submit" [disabled]="form.invalid || !file() || loading()" class="btn-primary">
        {{ loading() ? 'Enviando…' : 'Reenviar a revisión' }}
      </button>
    </form>
  `,
})
export class ResubmitForm implements OnInit {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly empresas = inject(EmpresaService);

  readonly empresa = input.required<EmpresaDetail>();
  readonly resubmitted = output<EmpresaDetail>();

  protected readonly form = this.fb.group({
    razon_social: ['', [Validators.required, Validators.minLength(2)]],
    rfc: ['', [Validators.required, Validators.minLength(12)]],
    sitio_web: ['', [Validators.required, Validators.minLength(3)]],
  });
  protected readonly file = signal<File | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);

  ngOnInit(): void {
    // Parte de los datos actuales para que el titular solo cambie lo que estaba mal.
    const { razon_social, rfc, sitio_web } = this.empresa();
    this.form.setValue({ razon_social, rfc, sitio_web });
  }

  protected onFile(event: Event): void {
    this.file.set((event.target as HTMLInputElement).files?.[0] ?? null);
  }

  protected submit(): void {
    const file = this.file();
    if (this.form.invalid || !file) return;
    this.loading.set(true);
    this.error.set(null);
    this.empresas.resubmit(this.form.getRawValue(), file).subscribe({
      next: (empresa) => this.resubmitted.emit(empresa),
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(apiErrorMessage(err, 'No se pudo reenviar la información.'));
      },
    });
  }
}
