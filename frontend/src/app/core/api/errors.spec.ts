import { HttpErrorResponse } from '@angular/common/http';
import { apiErrorMessage } from './errors';

const http = (status: number, error?: unknown) => new HttpErrorResponse({ status, error });

describe('apiErrorMessage', () => {
  it('usa el detalle de texto que manda la API', () => {
    expect(apiErrorMessage(http(409, { detail: 'Ya existe una cuenta con ese correo' }), 'x')).toBe(
      'Ya existe una cuenta con ese correo',
    );
  });

  it('traduce errores de validación con el nombre del campo', () => {
    const missing = { detail: [{ type: 'missing', loc: ['body', 'rfc'], msg: 'Field required' }] };
    expect(apiErrorMessage(http(422, missing), 'x')).toBe('RFC: es obligatorio');

    const rfc = {
      detail: [
        {
          type: 'value_error',
          loc: ['body', 'rfc'],
          msg: 'Value error, El RFC no tiene un formato válido',
        },
      ],
    };
    expect(apiErrorMessage(http(422, rfc), 'x')).toBe('RFC: El RFC no tiene un formato válido');

    const short = {
      detail: [{ type: 'string_too_short', loc: ['body', 'password'], msg: 'too short' }],
    };
    expect(apiErrorMessage(http(422, short), 'x')).toBe('Contraseña: es demasiado corto');
  });

  it('usa un texto genérico para validaciones desconocidas', () => {
    const other = { detail: [{ type: 'raro', loc: ['body', 'email'], msg: 'x' }] };
    expect(apiErrorMessage(http(422, other), 'x')).toBe('Correo: no es válido');
  });

  it('distingue falta de conexión y exceso de intentos', () => {
    expect(apiErrorMessage(http(0), 'x')).toContain('conexión');
    expect(apiErrorMessage(http(429), 'x')).toContain('Demasiados intentos');
  });

  it('cae al mensaje de respaldo en cualquier otro caso', () => {
    expect(apiErrorMessage(http(500, 'boom'), 'respaldo')).toBe('respaldo');
    expect(apiErrorMessage(new Error('x'), 'respaldo')).toBe('respaldo');
  });
});
