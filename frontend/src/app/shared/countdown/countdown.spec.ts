import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { Countdown } from './countdown';

describe('Countdown', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2030-01-01T10:00:00Z'));
  });
  afterEach(() => vi.useRealTimers());

  function create(secondsLeft: number) {
    const fixture = TestBed.createComponent(Countdown);
    const until = new Date(Date.now() + secondsLeft * 1000).toISOString();
    fixture.componentRef.setInput('until', until);
    const expired = vi.fn();
    fixture.componentInstance.expired.subscribe(expired);
    fixture.detectChanges();
    return {
      fixture,
      expired,
      text: () => (fixture.nativeElement as HTMLElement).textContent?.trim(),
    };
  }

  it('muestra minutos y segundos y cuenta hacia atrás', () => {
    const { fixture, text } = create(125);
    expect(text()).toBe('02:05');
    vi.advanceTimersByTime(5000);
    fixture.detectChanges();
    expect(text()).toBe('02:00');
  });

  it('avisa una sola vez al llegar a cero y no baja de 00:00', () => {
    const { fixture, expired, text } = create(2);
    vi.advanceTimersByTime(2000);
    fixture.detectChanges();
    expect(text()).toBe('00:00');
    expect(expired).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(5000);
    fixture.detectChanges();
    expect(text()).toBe('00:00');
    expect(expired).toHaveBeenCalledTimes(1);
    expect((fixture.nativeElement as HTMLElement).querySelector('span')?.className).toContain(
      'text-rose-700',
    );
  });

  it('una fecha ya vencida arranca en cero sin avisar de nuevo', () => {
    const { text, expired } = create(-30);
    expect(text()).toBe('00:00');
    expect(expired).not.toHaveBeenCalled();
  });
});
