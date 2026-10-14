import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { SpecField } from '../../core/api/models';

type SpecValue = string | number | boolean | null;
export type SpecGroup = FormGroup<Record<string, FormControl<SpecValue>>>;

/** Crea un control por cada especificación de la categoría, con los valores ya guardados si los hay. */
export function buildSpecGroup(
  fields: SpecField[],
  values: Record<string, unknown> = {},
): SpecGroup {
  const controls: Record<string, FormControl<SpecValue>> = {};
  for (const field of fields) {
    const saved = values[field.key] as SpecValue | undefined;
    const initial = saved ?? (field.type === 'boolean' ? false : null);
    controls[field.key] = new FormControl<SpecValue>(initial, {
      validators: field.required && field.type !== 'boolean' ? [Validators.required] : [],
    });
  }
  return new FormGroup(controls);
}

/** Valores listos para enviar a la API: sin campos vacíos y con el tipo correcto. */
export function specValues(fields: SpecField[], group: SpecGroup): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const field of fields) {
    const value = group.controls[field.key]?.value;
    if (value === null || value === undefined || value === '') continue;
    out[field.key] = field.type === 'number' ? Number(value) : value;
  }
  return out;
}

/** Campos de especificaciones de un equipo, según lo que define su categoría. */
@Component({
  selector: 'app-spec-fields',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div [formGroup]="group()" class="grid gap-3 sm:grid-cols-2">
      @for (field of fields(); track field.key) {
        @if (field.type === 'boolean') {
          <label class="flex items-center gap-2 pt-6 text-sm font-semibold">
            <input type="checkbox" [formControlName]="field.key" class="size-4" />
            {{ field.label }}
          </label>
        } @else {
          <div>
            <label [for]="'spec-' + field.key" class="label">
              {{ field.label }}{{ field.unit ? ' (' + field.unit + ')' : ''
              }}{{ field.required ? ' *' : '' }}
            </label>
            @if (field.type === 'select') {
              <select [id]="'spec-' + field.key" [formControlName]="field.key" class="input">
                <option [ngValue]="null">—</option>
                @for (option of field.options; track option) {
                  <option [value]="option">{{ option }}</option>
                }
              </select>
            } @else {
              <input
                [id]="'spec-' + field.key"
                [type]="field.type === 'number' ? 'number' : 'text'"
                [attr.step]="field.type === 'number' ? 'any' : null"
                [formControlName]="field.key"
                class="input"
              />
            }
          </div>
        }
      }
    </div>
  `,
})
export class SpecFields {
  readonly fields = input.required<SpecField[]>();
  readonly group = input.required<SpecGroup>();
}
