import { DestroyRef, Injectable, inject } from '@angular/core';
import { SwUpdate, VersionReadyEvent } from '@angular/service-worker';
import { filter } from 'rxjs';

/** Cada cuánto se busca una versión nueva mientras la app sigue abierta. */
const REVISAR_CADA_MS = 5 * 60 * 1000;

/**
 * Mantiene la app al día. El service worker guarda la versión instalada para que abra rápido
 * (y sin conexión), pero por sí solo mostraría la versión anterior hasta recargar dos veces: aquí,
 * en cuanto hay una nueva lista se activa y se recarga la página.
 */
@Injectable({ providedIn: 'root' })
export class UpdateService {
  private readonly updates = inject(SwUpdate);
  private readonly destroyRef = inject(DestroyRef);

  /** Se llama una vez al arrancar. Sin service worker (desarrollo) no hace nada. */
  start(reload: () => void = () => document.location.reload()): void {
    if (!this.updates.isEnabled) return;

    const subscription = this.updates.versionUpdates
      .pipe(filter((event): event is VersionReadyEvent => event.type === 'VERSION_READY'))
      .subscribe(() => {
        void this.updates.activateUpdate().then(reload);
      });
    this.destroyRef.onDestroy(() => subscription.unsubscribe());

    const check = (): void => {
      void this.updates.checkForUpdate().catch(() => undefined); // sin red: se reintenta luego
    };
    const timer = setInterval(check, REVISAR_CADA_MS);
    this.destroyRef.onDestroy(() => clearInterval(timer));
    // Al volver a la pestaña también se revisa: es cuando más se nota una versión vieja.
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') check();
    });
    check();
  }
}
