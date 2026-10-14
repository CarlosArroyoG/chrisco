import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  input,
  OnInit,
  output,
  signal,
} from '@angular/core';

/** Cuenta regresiva hasta `until` (ISO). Avisa con `expired` cuando llega a cero. */
@Component({
  selector: 'app-countdown',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="font-mono font-bold" [class]="remaining() > 0 ? '' : 'text-rose-700'">{{
    text()
  }}</span>`,
})
export class Countdown implements OnInit {
  private readonly destroyRef = inject(DestroyRef);

  readonly until = input.required<string>();
  readonly expired = output<void>();

  /** Segundos que faltan (nunca negativo). */
  protected readonly remaining = signal(0);
  protected readonly text = computed(() => {
    const total = this.remaining();
    const minutes = Math.floor(total / 60);
    const seconds = total % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  });

  ngOnInit(): void {
    this.tick();
    const timer = setInterval(() => this.tick(), 1000);
    this.destroyRef.onDestroy(() => clearInterval(timer));
  }

  private tick(): void {
    const left = Math.max(0, Math.ceil((new Date(this.until()).getTime() - Date.now()) / 1000));
    const wasRunning = this.remaining() > 0;
    this.remaining.set(left);
    if (left === 0 && wasRunning) this.expired.emit();
  }
}
