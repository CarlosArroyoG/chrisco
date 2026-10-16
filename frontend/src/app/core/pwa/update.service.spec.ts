import { TestBed } from '@angular/core/testing';
import { SwUpdate, VersionEvent } from '@angular/service-worker';
import { Subject } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { UpdateService } from './update.service';

function setup(enabled: boolean) {
  const versionUpdates = new Subject<VersionEvent>();
  const swUpdate = {
    isEnabled: enabled,
    versionUpdates,
    activateUpdate: vi.fn().mockResolvedValue(true),
    checkForUpdate: vi.fn().mockResolvedValue(false),
  };
  TestBed.configureTestingModule({ providers: [{ provide: SwUpdate, useValue: swUpdate }] });
  return { swUpdate, versionUpdates, service: TestBed.inject(UpdateService) };
}

describe('UpdateService', () => {
  it('sin service worker (desarrollo) no hace nada', () => {
    const { service, swUpdate } = setup(false);
    const reload = vi.fn();
    service.start(reload);
    expect(swUpdate.checkForUpdate).not.toHaveBeenCalled();
    expect(reload).not.toHaveBeenCalled();
  });

  it('revisa al arrancar y, cuando hay versión nueva, la activa y recarga', async () => {
    const { service, swUpdate, versionUpdates } = setup(true);
    const reload = vi.fn();
    service.start(reload);
    expect(swUpdate.checkForUpdate).toHaveBeenCalledTimes(1);

    versionUpdates.next({ type: 'VERSION_DETECTED', version: { hash: 'b' } });
    await Promise.resolve();
    expect(reload).not.toHaveBeenCalled(); // solo detectada: todavía no está lista

    versionUpdates.next({
      type: 'VERSION_READY',
      currentVersion: { hash: 'a' },
      latestVersion: { hash: 'b' },
    });
    await vi.waitFor(() => expect(reload).toHaveBeenCalledTimes(1));
    expect(swUpdate.activateUpdate).toHaveBeenCalledTimes(1);
  });

  it('si no hay red al revisar, no falla', async () => {
    const { service, swUpdate } = setup(true);
    swUpdate.checkForUpdate.mockRejectedValue(new Error('offline'));
    expect(() => service.start(vi.fn())).not.toThrow();
    await Promise.resolve();
  });
});
