import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { Observable, Subject, of, throwError } from 'rxjs';
import { Page } from './models';
import { PagedList, pagedList } from './paged-list';

/** Componente mínimo: `pagedList` necesita un contexto de inyección, igual que en la app. */
function setup(fetch: (page: number) => Observable<Page<string>>): PagedList<string> {
  let list!: PagedList<string>;
  @Component({ selector: 'app-host', template: '' })
  class Host {
    constructor() {
      list = pagedList<string>({ pageSize: 10, fetch, errorMessage: 'Falló' });
    }
  }
  TestBed.createComponent(Host);
  return list;
}

describe('pagedList', () => {
  it('carga la página pedida y calcula el total de páginas', () => {
    const list = setup((page) => of({ items: [`p${page}`], total: 25 }));
    list.go(2);
    expect(list.items()).toEqual(['p2']);
    expect(list.page()).toBe(2);
    expect(list.pages()).toBe(3);
    expect(list.loaded()).toBe(true);
    expect(list.error()).toBeNull();
  });

  it('con cero resultados hay una página, no cero', () => {
    const list = setup(() => of({ items: [], total: 0 }));
    list.go(0);
    expect(list.pages()).toBe(1);
  });

  it('una respuesta vieja no pisa a la nueva', () => {
    const lenta = new Subject<Page<string>>();
    const rapida = new Subject<Page<string>>();
    const sources = [lenta, rapida];
    let call = 0;
    const list = setup(() => sources[call++].asObservable());

    list.go(0); // primera petición, aún sin respuesta
    list.go(0); // segunda petición: cancela a la primera
    rapida.next({ items: ['nueva'], total: 1 });
    lenta.next({ items: ['vieja'], total: 1 }); // llega tarde y se descarta
    expect(list.items()).toEqual(['nueva']);
  });

  it('muestra un mensaje si falla y se recupera con la siguiente petición', () => {
    let fail = true;
    const list = setup(() =>
      fail
        ? throwError(() => new HttpErrorResponse({ status: 500 }))
        : of({ items: ['ok'], total: 1 }),
    );
    list.go(0);
    expect(list.error()).toBe('Falló');
    expect(list.loaded()).toBe(true);
    fail = false;
    list.go(0);
    expect(list.error()).toBeNull();
    expect(list.items()).toEqual(['ok']);
  });
});
