import { fotoUrl, toParams } from './catalogo.service';

describe('catalogo helpers', () => {
  it('toParams omite lo vacío y conserva ceros y falsos', () => {
    const params = toParams({
      q: 'cat',
      categoria_id: '',
      limit: 0,
      dry_run: false,
      offset: undefined,
      x: null,
    });
    expect(params.keys().sort()).toEqual(['dry_run', 'limit', 'q']);
    expect(params.get('limit')).toBe('0');
    expect(params.get('dry_run')).toBe('false');
  });

  it('fotoUrl apunta a la API según el tamaño', () => {
    expect(fotoUrl('abc', 'thumb')).toBe('/api/equipos/fotos/abc/thumb');
    expect(fotoUrl('abc', 'full')).toBe('/api/equipos/fotos/abc/full');
  });
});
