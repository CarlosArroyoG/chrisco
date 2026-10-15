#!/bin/sh
# Tareas programadas de CHRISCO Go (corre en su propio contenedor, con la misma imagen del API):
#   - cada minuto: vence las reservas provisionales caducadas.
#   - cada día a las 08:00 (hora del negocio): avisa por correo de los mantenimientos próximos o vencidos.
set -eu

ultimo_aviso=""
while true; do
    python -m app.cli expire-holds || echo "expire-holds falló; se reintenta en un minuto"

    hoy="$(TZ="${TIMEZONE:-America/Mexico_City}" date +%F)"
    hora="$(TZ="${TIMEZONE:-America/Mexico_City}" date +%H)"
    if [ "$hora" -ge 8 ] && [ "$ultimo_aviso" != "$hoy" ]; then
        if python -m app.cli send-maintenance-alerts; then
            ultimo_aviso="$hoy"
        else
            echo "send-maintenance-alerts falló; se reintenta en un minuto"
        fi
    fi
    sleep 60
done
