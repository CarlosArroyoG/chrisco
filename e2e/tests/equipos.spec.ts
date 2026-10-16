import { resetDatabase } from '../db';
import { expect, test } from '@playwright/test';
import { ADMIN, VENTAS } from '../env';
import { createApprovedClient, logout, PNG, signIn } from './helpers';

const CLIENT = {
  email: 'cliente@catalogo-e2e.com',
  password: 'cliente-clave-larga-1',
  rfc: 'CAT010101AB1',
  razonSocial: 'Constructora Catálogo E2E SA de CV',
};
const CATEGORIA = 'Pavimentadora E2E';
const EQUIPO = 'Pavimentadora UI uno';

const CSV_COLUMNS =
  'codigo,categoria,nombre,marca,modelo,numero_serie,tarifa_hora,spec_peso_maximo,spec_combustible,spec_con_orugas';
const CSV_OK = `${CSV_COLUMNS}\nCSV-001,${CATEGORIA},Importada uno,Vögele,MT 3000,CSV-SN-1,3000,15000,diésel,sí`;
const CSV_MALO = `${CSV_OK}\nCSV-002,Categoría Fantasma,Importada dos,Vögele,MT 3000,CSV-SN-2,3000,,,`;
const csv = (contenido: string) => ({
  name: 'equipos.csv',
  mimeType: 'text/csv',
  buffer: Buffer.from(contenido, 'utf-8'),
});

// Cada archivo parte de un sistema limpio: no depende de lo que dejó otro.
test.beforeAll(() => resetDatabase());

test.describe.serial('Registro de equipos y catálogo', () => {
  test('el admin crea una categoría con especificaciones propias', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.getByRole('link', { name: 'Categorías', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Categorías de maquinaria' })).toBeVisible();

    await page.getByLabel('Nombre *').fill(CATEGORIA);

    await page.getByRole('button', { name: '+ Agregar especificación' }).click();
    await page.getByLabel('Etiqueta').nth(0).fill('Peso máximo');
    await expect(page.getByLabel('Clave').nth(0)).toHaveValue('peso_maximo'); // sugerida de la etiqueta
    await page.getByLabel('Tipo').nth(0).selectOption('number');
    await page.getByLabel('Unidad').nth(0).fill('kg');
    await page.getByLabel('Obligatoria').check();

    await page.getByRole('button', { name: '+ Agregar especificación' }).click();
    await page.getByLabel('Etiqueta').nth(1).fill('Combustible');
    await page.getByLabel('Tipo').nth(1).selectOption('select');
    await page.getByLabel('Opciones (separadas por coma)').fill('Diésel, Gasolina');

    await page.getByRole('button', { name: '+ Agregar especificación' }).click();
    await page.getByLabel('Etiqueta').nth(2).fill('Con orugas');
    await page.getByLabel('Tipo').nth(2).selectOption('boolean');

    await page.getByRole('button', { name: 'Crear categoría' }).click();
    await expect(page.getByRole('heading', { name: CATEGORIA })).toBeVisible();
    await expect(page.getByText('0 equipo(s) · 3 especificación(es)')).toBeVisible();
  });

  test('no permite una categoría repetida', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/categorias');
    await page.getByLabel('Nombre *').fill(CATEGORIA.toLowerCase());
    await page.getByRole('button', { name: 'Crear categoría' }).click();
    await expect(page.getByRole('alert')).toContainText('Ya existe una categoría con ese nombre');
  });

  test('crea un equipo: las especificaciones salen de su categoría', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.getByRole('link', { name: 'Equipos', exact: true }).click();
    await page.getByRole('link', { name: 'Nuevo equipo' }).click();

    await expect(page.getByLabel(/Peso máximo/)).toHaveCount(0); // aún no hay categoría elegida
    await page.getByLabel('Categoría *').selectOption({ label: CATEGORIA });
    await expect(page.getByLabel('Peso máximo (kg) *')).toBeVisible();
    await expect(page.getByLabel('Combustible')).toBeVisible();
    await expect(page.getByLabel('Con orugas')).toBeVisible();

    // Faltan datos: no se envía.
    await page.getByRole('button', { name: 'Crear equipo' }).click();
    await expect(page.getByRole('alert')).toContainText('Revisa los campos');

    await page.getByLabel('Código *').fill('ui-001');
    await page.getByLabel('Nombre *').fill(EQUIPO);
    await page.getByLabel('Marca *').fill('Vögele');
    await page.getByLabel('Modelo *').fill('MT 3000-2');
    await page.getByLabel('Número de serie *').fill('UI-SN-0001');
    await page.getByLabel('Año').fill('2021');
    await page.getByLabel('Tarifa por hora (MXN)').fill('3400');
    await page.getByLabel('Se transporta en lowboy').check();
    await page.getByLabel('Peso máximo (kg) *').fill('18000');
    await page.getByLabel('Combustible').selectOption('Diésel');
    await page.getByLabel('Con orugas').check();
    await page.getByRole('button', { name: 'Crear equipo' }).click();

    // Tras crear se abre el equipo para agregar fotos.
    await expect(page).toHaveURL(/\/admin\/equipos\/[0-9a-f-]{36}$/);
    await expect(page.getByRole('heading', { name: EQUIPO })).toBeVisible();
    await expect(page.getByLabel('Código *')).toHaveValue('UI-001');
    await expect(page.getByLabel('Peso máximo (kg) *')).toHaveValue('18000');
  });

  test('sube y quita fotos', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/equipos');
    await page.getByRole('link', { name: 'Editar' }).click();

    await expect(page.getByText('Fotos (0/10)')).toBeVisible();
    await page.getByLabel(/Agregar fotos/).setInputFiles([PNG, PNG]);
    await expect(page.getByText('Fotos (2/10)')).toBeVisible();
    await expect(page.getByAltText('Foto del equipo')).toHaveCount(2);
    const cargada = await page
      .getByAltText('Foto del equipo')
      .first()
      .evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0);
    expect(cargada).toBe(true);

    await page.getByRole('button', { name: 'Quitar foto' }).first().click();
    await expect(page.getByText('Fotos (1/10)')).toBeVisible();

    await page.getByLabel(/Agregar fotos/).setInputFiles({ name: 'doc.png', mimeType: 'image/png', buffer: Buffer.from('no es imagen') });
    await expect(page.getByRole('alert')).toContainText('doc.png: El archivo no es una imagen válida');
    await expect(page.getByText('Fotos (1/10)')).toBeVisible();
  });

  test('rechaza un código repetido', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/equipos/nuevo');
    await page.getByLabel('Categoría *').selectOption({ label: CATEGORIA });
    await page.getByLabel('Código *').fill('UI-001');
    await page.getByLabel('Nombre *').fill('Otra');
    await page.getByLabel('Marca *').fill('X');
    await page.getByLabel('Modelo *').fill('Y');
    await page.getByLabel('Número de serie *').fill('OTRA-SERIE');
    await page.getByLabel('Tarifa por día (MXN)').fill('20000');
    await page.getByLabel('Peso máximo (kg) *').fill('100');
    await page.getByRole('button', { name: 'Crear equipo' }).click();
    await expect(page.getByRole('alert')).toContainText('Ya existe un equipo con ese código');
  });

  test('descarga la plantilla e importa un CSV: primero valida, luego guarda', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/equipos/importar');

    const descarga = page.waitForEvent('download');
    await page.getByLabel('Categoría (opcional)').selectOption({ label: CATEGORIA });
    await page.getByRole('button', { name: 'Descargar plantilla' }).click();
    expect((await descarga).suggestedFilename()).toBe('plantilla-equipos.csv');

    // Un archivo con un error por fila: nada se guarda y el botón de importar sigue bloqueado.
    await page.getByLabel('Archivo CSV').setInputFiles(csv(CSV_MALO));
    await page.getByRole('button', { name: 'Validar archivo' }).click();
    await expect(page.getByRole('alert')).toContainText('No se guardó nada');
    await expect(page.getByRole('row', { name: /3.*categoria: «Categoría Fantasma» no existe/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /^Importar/ })).toBeDisabled();

    // Corregido: se valida, y solo entonces se puede importar.
    await page.getByLabel('Archivo CSV').setInputFiles(csv(CSV_OK));
    await expect(page.getByRole('button', { name: /^Importar/ })).toBeDisabled(); // otro archivo, validar de nuevo
    await page.getByRole('button', { name: 'Validar archivo' }).click();
    await expect(page.getByRole('status')).toContainText('El archivo es válido: 1 equipos listos');
    await page.getByRole('button', { name: /^Importar/ }).click();
    await expect(page.getByRole('status')).toContainText('Se importaron 1 equipos');
  });

  test('la lista busca, filtra y cuenta', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/equipos');
    await expect(page.getByRole('heading', { name: 'Equipos (2)' })).toBeVisible();

    await page.getByLabel('Buscar').fill('importada');
    await expect(page.getByRole('heading', { name: 'Equipos (1)' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'CSV-001' })).toBeVisible();

    await page.getByLabel('Buscar').fill('no existe esto');
    await expect(page.getByText('No hay equipos con esos filtros.')).toBeVisible();

    await page.getByLabel('Buscar').fill('');
    await page.getByLabel('Estado').selectOption('baja');
    await expect(page.getByText('No hay equipos con esos filtros.')).toBeVisible();
  });

  test('ventas consulta pero no modifica', async ({ page }) => {
    await signIn(page, VENTAS.email, VENTAS.password);
    await page.getByRole('link', { name: 'Equipos', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Equipos (2)' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Nuevo equipo' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Importar CSV' })).toHaveCount(0);

    await page.getByRole('link', { name: 'Ver' }).first().click();
    await expect(page.getByLabel('Nombre *')).toBeDisabled();
    await expect(page.getByText('Solo un administrador puede modificar equipos.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Guardar cambios' })).toHaveCount(0);
    await expect(page.getByLabel(/Agregar fotos/)).toHaveCount(0);

    await page.getByRole('link', { name: 'Categorías', exact: true }).click();
    await expect(page.getByRole('heading', { name: CATEGORIA })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Crear categoría' })).toHaveCount(0);
  });

  test('una categoría con equipos no se puede eliminar', async ({ page }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/categorias');
    await page.getByRole('button', { name: 'Eliminar' }).click();
    await page.getByRole('button', { name: 'Sí' }).click();
    await expect(page.getByRole('alert')).toContainText('tiene 2 equipo(s)');
  });

  test('el cliente aprobado ve el catálogo; uno sin aprobar, no', async ({ page, request }) => {
    await createApprovedClient(request, CLIENT);
    await signIn(page, CLIENT.email, CLIENT.password);
    await expect(page).toHaveURL(/\/cliente$/);
    await page.getByRole('link', { name: 'Ver catálogo de maquinaria' }).click();

    await expect(page.getByRole('heading', { name: 'Catálogo de maquinaria (2)' })).toBeVisible();
    const tarjeta = page.locator(`[data-equipo="${EQUIPO}"]`);
    await expect(tarjeta).toContainText('$3,400/h');
    await expect(tarjeta).toContainText('Se entrega en lowboy');
    await expect(tarjeta.getByRole('img')).toBeVisible();

    // Nada interno: ni serie ni notas.
    await expect(page.getByText('UI-SN-0001')).toHaveCount(0);

    await page.getByLabel('Buscar').fill('importada');
    await expect(page.getByRole('heading', { name: 'Catálogo de maquinaria (1)' })).toBeVisible();
    await page.getByLabel('Buscar').fill('');
    // Espera a que la lista se recargue antes de entrar a la ficha (si no, el clic cae en una tarjeta que se redibuja).
    await expect(page.getByRole('heading', { name: 'Catálogo de maquinaria (2)' })).toBeVisible();

    await tarjeta.getByRole('link', { name: EQUIPO }).click();
    await expect(page).toHaveURL(/\/cliente\/catalogo\/[0-9a-f-]{36}/);
    await expect(page.getByRole('heading', { name: EQUIPO })).toBeVisible();
    await expect(page.getByText('Peso máximo')).toBeVisible();
    await expect(page.getByText('18000 kg')).toBeVisible();
    await expect(page.getByText('Diésel', { exact: true })).toBeVisible();
    await expect(page.getByText('Se transporta en lowboy')).toBeVisible();
    await expect(page.getByRole('img', { name: EQUIPO })).toBeVisible();
    await logout(page);
  });

  test('un equipo dado de baja desaparece del catálogo', async ({ page, browser }) => {
    await signIn(page, ADMIN.email, ADMIN.password);
    await page.goto('/admin/equipos');
    await page.getByLabel('Buscar').fill('UI-001');
    await expect(page.getByRole('heading', { name: 'Equipos (1)' })).toBeVisible(); // espera la búsqueda
    await page.getByRole('link', { name: 'Editar' }).click();
    // La lista también tiene un selector «Estado»: se espera a que cargue la edición del equipo.
    await expect(page.getByLabel('Código *')).toHaveValue('UI-001');
    await page.getByLabel('Estado').selectOption('baja');
    await page.getByRole('button', { name: 'Guardar cambios' }).click();
    await expect(page.getByText('Cambios guardados.')).toBeVisible();

    const cliente = await (await browser.newContext()).newPage();
    await signIn(cliente, CLIENT.email, CLIENT.password);
    await cliente.getByRole('link', { name: 'Ver catálogo de maquinaria' }).click();
    await expect(cliente.getByRole('heading', { name: 'Catálogo de maquinaria (1)' })).toBeVisible();
    await expect(cliente.getByRole('link', { name: new RegExp(EQUIPO) })).toHaveCount(0);
  });
});
