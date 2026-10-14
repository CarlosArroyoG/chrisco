import { slugify } from './categorias-page';

describe('slugify', () => {
  it('quita acentos, mayúsculas y símbolos', () => {
    expect(slugify('Peso máximo')).toBe('peso_maximo');
    expect(slugify('  Capacidad (m³)  ')).toBe('capacidad_m');
    expect(slugify('Año de fabricación')).toBe('ano_de_fabricacion');
  });

  it('siempre empieza con letra, como pide la API', () => {
    expect(slugify('4x4')).toBe('c_4x4');
    expect(slugify('123')).toBe('c_123');
  });

  it('devuelve vacío si no queda nada utilizable y limita la longitud', () => {
    expect(slugify('¿¡?!')).toBe('');
    expect(slugify('a'.repeat(80))).toHaveLength(40);
    expect(slugify('1' + 'a'.repeat(80))).toHaveLength(40);
  });
});
