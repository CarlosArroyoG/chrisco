import { SpecField } from '../../core/api/models';
import { buildSpecGroup, specValues } from './spec-fields';

const FIELDS: SpecField[] = [
  { key: 'peso_kg', label: 'Peso', type: 'number', unit: 'kg', required: true },
  { key: 'motor', label: 'Motor', type: 'text' },
  { key: 'combustible', label: 'Combustible', type: 'select', options: ['Diésel', 'Gasolina'] },
  { key: 'oruga', label: 'Con orugas', type: 'boolean' },
];

describe('especificaciones dinámicas', () => {
  it('crea un control por campo con los valores guardados', () => {
    const group = buildSpecGroup(FIELDS, { peso_kg: 18000, oruga: true, viejo: 'x' });
    expect(Object.keys(group.controls)).toEqual(['peso_kg', 'motor', 'combustible', 'oruga']);
    expect(group.controls['peso_kg'].value).toBe(18000);
    expect(group.controls['oruga'].value).toBe(true);
    expect(group.controls['motor'].value).toBeNull();
  });

  it('solo los campos obligatorios (no booleanos) exigen valor', () => {
    const group = buildSpecGroup(FIELDS);
    expect(group.invalid).toBe(true);
    group.controls['peso_kg'].setValue(10);
    expect(group.valid).toBe(true);
    expect(group.controls['oruga'].value).toBe(false); // un sí/no sin marcar vale «no»
  });

  it('envía solo lo capturado y con el tipo correcto', () => {
    const group = buildSpecGroup(FIELDS);
    group.controls['peso_kg'].setValue('18000' as unknown as number);
    group.controls['motor'].setValue('');
    expect(specValues(FIELDS, group)).toEqual({ peso_kg: 18000, oruga: false });
  });

  it('conserva texto y opciones tal cual', () => {
    const group = buildSpecGroup(FIELDS, { peso_kg: 1, motor: 'Cummins', combustible: 'Diésel' });
    expect(specValues(FIELDS, group)).toEqual({
      peso_kg: 1,
      motor: 'Cummins',
      combustible: 'Diésel',
      oruga: false,
    });
  });
});
