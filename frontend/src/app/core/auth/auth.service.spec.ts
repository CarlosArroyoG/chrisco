import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { authInterceptor } from './auth.interceptor';
import { User } from './auth.models';
import { API_URL, AuthService } from './auth.service';

const USER: User = { id: '1', email: 'a@b.com', full_name: 'Ana', role: 'admin' };
const TOKENS = { access_token: 'acc-1', refresh_token: 'ref-1', token_type: 'bearer' };

describe('AuthService + interceptor', () => {
  let auth: AuthService;
  let http: HttpTestingController;
  let client: HttpClient;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: 'login', children: [] }]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
    client = TestBed.inject(HttpClient);
  });

  afterEach(() => http.verify());

  function doLogin(): void {
    auth.login('a@b.com', 'x').subscribe();
    http.expectOne(`${API_URL}/auth/login`).flush(TOKENS);
    http.expectOne(`${API_URL}/auth/me`).flush(USER);
  }

  it('login guarda tokens, carga el usuario y adjunta el bearer', () => {
    doLogin();
    expect(auth.user()).toEqual(USER);
    expect(localStorage.getItem('chrisco.refresh_token')).toBe('ref-1');
    expect(auth.token).toBe('acc-1');
  });

  it('el login no lleva Authorization', () => {
    auth.login('a@b.com', 'x').subscribe();
    const req = http.expectOne(`${API_URL}/auth/login`);
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush(TOKENS);
    http.expectOne(`${API_URL}/auth/me`).flush(USER);
  });

  it('ante un 401 renueva el token una sola vez y repite la petición', () => {
    doLogin();
    let result: unknown;
    client.get(`${API_URL}/algo`).subscribe((r) => (result = r));

    http.expectOne(`${API_URL}/algo`).flush(null, { status: 401, statusText: 'No autorizado' });
    http
      .expectOne(`${API_URL}/auth/refresh`)
      .flush({ ...TOKENS, access_token: 'acc-2', refresh_token: 'ref-2' });
    const retry = http.expectOne(`${API_URL}/algo`);
    expect(retry.request.headers.get('Authorization')).toBe('Bearer acc-2');
    retry.flush({ ok: true });

    expect(result).toEqual({ ok: true });
    expect(localStorage.getItem('chrisco.refresh_token')).toBe('ref-2');
  });

  it('si la renovación falla, cierra la sesión', () => {
    doLogin();
    let failed = false;
    client.get(`${API_URL}/algo`).subscribe({ error: () => (failed = true) });

    http.expectOne(`${API_URL}/algo`).flush(null, { status: 401, statusText: 'x' });
    http.expectOne(`${API_URL}/auth/refresh`).flush(null, { status: 401, statusText: 'x' });

    expect(failed).toBe(true);
    expect(auth.user()).toBeNull();
    expect(localStorage.getItem('chrisco.refresh_token')).toBeNull();
  });

  it('restoreSession recupera al usuario con un refresh token guardado', () => {
    localStorage.setItem('chrisco.refresh_token', 'ref-1');
    auth.restoreSession().subscribe();
    http.expectOne(`${API_URL}/auth/refresh`).flush(TOKENS);
    http.expectOne(`${API_URL}/auth/me`).flush(USER);
    expect(auth.isAuthenticated()).toBe(true);
  });

  it('restoreSession sin refresh token no hace peticiones', () => {
    auth.restoreSession().subscribe();
    http.expectNone(`${API_URL}/auth/refresh`);
    expect(auth.isAuthenticated()).toBe(false);
  });

  it('restoreSession con refresh token inválido limpia todo', () => {
    localStorage.setItem('chrisco.refresh_token', 'viejo');
    auth.restoreSession().subscribe();
    http.expectOne(`${API_URL}/auth/refresh`).flush(null, { status: 401, statusText: 'x' });
    expect(auth.user()).toBeNull();
    expect(localStorage.getItem('chrisco.refresh_token')).toBeNull();
  });
});
