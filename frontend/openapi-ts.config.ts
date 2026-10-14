import { defineConfig } from '@hey-api/openapi-ts';

// Genera solo los tipos de la API a partir del OpenAPI de FastAPI (`npm run api:gen`).
export default defineConfig({
  input: 'openapi.json',
  output: { path: 'src/app/core/api/generated', clean: true },
  plugins: ['@hey-api/typescript'],
});
