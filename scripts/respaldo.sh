#!/bin/sh
# Respaldo de CHRISCO Go: la base de datos y los archivos privados (constancias, licencias,
# comprobantes, fotos). Uso:  ./scripts/respaldo.sh [carpeta-destino]
# Programarlo a diario (cron) y copiar la carpeta fuera del servidor.
set -eu

destino="${1:-./respaldos}"
fecha="$(date +%Y%m%d-%H%M%S)"
compose="docker compose -f docker-compose.prod.yml --env-file .env.production"
mkdir -p "$destino"

$compose exec -T db pg_dump -U chrisco -d chrisco --format=custom > "$destino/db-$fecha.dump"
$compose exec -T api tar -C /data -czf - uploads > "$destino/archivos-$fecha.tar.gz"

# Conserva los últimos 14 respaldos de cada tipo.
for tipo in db archivos; do
    ls -1t "$destino"/"$tipo"-* 2>/dev/null | tail -n +15 | xargs -r rm --
done
echo "Respaldo listo en $destino ($fecha)"
echo "Restaurar la base: docker compose ... exec -T db pg_restore -U chrisco -d chrisco --clean < db-$fecha.dump"
