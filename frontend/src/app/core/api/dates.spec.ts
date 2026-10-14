import { periodFromInputs, toLocalInput } from './dates';

describe('fechas de formularios', () => {
  it('convierte dos inputs válidos a un periodo en UTC', () => {
    const periodo = periodFromInputs('2030-05-01T08:00', '2030-05-01T18:30');
    expect(periodo).not.toBeNull();
    expect(new Date(periodo!.desde).getTime()).toBe(new Date('2030-05-01T08:00').getTime());
    expect(periodo!.hasta.endsWith('Z')).toBe(true);
  });

  it('rechaza periodos incompletos, invertidos o ilegibles', () => {
    expect(periodFromInputs('', '2030-05-01T18:00')).toBeNull();
    expect(periodFromInputs('2030-05-01T08:00', '')).toBeNull();
    expect(periodFromInputs('2030-05-02T08:00', '2030-05-01T08:00')).toBeNull();
    expect(periodFromInputs('2030-05-01T08:00', '2030-05-01T08:00')).toBeNull();
    expect(periodFromInputs('no es fecha', '2030-05-01T08:00')).toBeNull();
  });

  it('toLocalInput usa la hora local y rellena con ceros', () => {
    expect(toLocalInput(new Date(2030, 0, 5, 7, 3))).toBe('2030-01-05T07:03');
  });

  it('ida y vuelta: lo que se escribe es el mismo instante', () => {
    const date = new Date(2031, 6, 9, 15, 45);
    const periodo = periodFromInputs(
      toLocalInput(date),
      toLocalInput(new Date(date.getTime() + 3600_000)),
    );
    expect(new Date(periodo!.desde).getTime()).toBe(date.getTime());
  });
});
