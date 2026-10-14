"""Reglas de disponibilidad: sin dobles reservas, vencimientos y ciclo de vida de una reserva."""

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import cli
from app.core.errors import Conflict, InvalidInput
from app.db.session import SessionLocal
from app.models.bloqueo import Bloqueo, BloqueoEstado, BloqueoTipo
from app.models.equipo import Equipo, EquipoStatus
from app.schemas.disponibilidad import EstadoActual
from app.services import accounts, disponibilidad

NOW = datetime.now(UTC).replace(microsecond=0)


def h(hours: float) -> datetime:
    return NOW + timedelta(hours=hours)


@pytest.fixture
def equipo(db, make_equipo) -> Equipo:
    return db.get(Equipo, uuid.UUID(make_equipo()["id"]))


@pytest.fixture
def user(db, admin_h):
    """El administrador de pruebas (lo crea `admin_h`)."""
    return accounts.get_by_email(db, "admin@chrisco-pruebas.com")


def put_block(db, equipo, user, a, b, tipo=BloqueoTipo.MANTENIMIENTO):
    return disponibilidad.block(db, equipo, tipo, h(a), h(b), "motivo de prueba", user)


# ---------------------------------------------------------------- sin dobles reservas


def test_periodos_que_se_traslapan_no_conviven(db, equipo, user) -> None:
    put_block(db, equipo, user, 10, 12)
    for a, b in ((11, 13), (9, 11), (10, 12), (9, 13), (10.5, 11.5)):
        with pytest.raises(Conflict, match="no está disponible"):
            put_block(db, equipo, user, a, b)


def test_periodos_contiguos_si_conviven(db, equipo, user) -> None:
    put_block(db, equipo, user, 10, 12)
    put_block(db, equipo, user, 12, 14)  # justo donde termina el anterior
    put_block(db, equipo, user, 8, 10)  # justo donde empieza
    assert len(disponibilidad.overlapping(db, equipo.id, h(0), h(24))) == 3


def test_dos_equipos_distintos_no_se_estorban(db, make_equipo, user) -> None:
    a = db.get(Equipo, uuid.UUID(make_equipo()["id"]))
    b = db.get(Equipo, uuid.UUID(make_equipo()["id"]))
    put_block(db, a, user, 10, 12)
    put_block(db, b, user, 10, 12)


def test_la_base_de_datos_impide_el_traslape_aunque_se_salte_el_servicio(db, equipo) -> None:
    def raw(a, b):
        db.add(
            Bloqueo(
                equipo_id=equipo.id,
                tipo=BloqueoTipo.MANUAL,
                periodo=disponibilidad.period(h(a), h(b)),
                motivo="x",
            )
        )
        db.commit()

    raw(1, 3)
    with pytest.raises(IntegrityError) as error:
        raw(2, 4)
    assert error.value.orig.sqlstate == "23P01"  # exclusion_violation
    db.rollback()


def test_un_bloqueo_liberado_o_expirado_ya_no_estorba_en_la_base(db, equipo, user) -> None:
    primero = put_block(db, equipo, user, 1, 3)
    disponibilidad.release(db, primero)
    put_block(db, equipo, user, 2, 4)  # el liberado ya no cuenta


@pytest.mark.parametrize(
    "mal",
    [
        {"tipo": BloqueoTipo.SOLICITUD},  # provisional sin vencimiento
        {"tipo": BloqueoTipo.RENTA, "vence_en": NOW},  # firme con vencimiento
        {"tipo": BloqueoTipo.MANUAL},  # del personal sin motivo
    ],
)
def test_la_base_de_datos_valida_la_coherencia_del_bloqueo(db, equipo, mal) -> None:
    db.add(Bloqueo(equipo_id=equipo.id, periodo=disponibilidad.period(h(1), h(2)), **mal))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_un_periodo_vacio_no_se_guarda(db, equipo) -> None:
    db.add(
        Bloqueo(
            equipo_id=equipo.id,
            tipo=BloqueoTipo.MANUAL,
            periodo=disponibilidad.period(h(1), h(1)),
            motivo="x",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_dos_reservas_simultaneas_del_mismo_equipo_solo_dejan_una(db, equipo, user) -> None:
    """El caso real: dos clientes piden la misma máquina al mismo tiempo."""
    n = 6
    barrier = threading.Barrier(n)
    results: list[str] = []

    def pedir() -> None:
        with SessionLocal() as session:
            e = session.get(Equipo, equipo.id)
            u = accounts.get_by_email(session, "admin@chrisco-pruebas.com")
            barrier.wait()
            try:
                disponibilidad.place_hold(session, e, h(1), h(5), u)
                results.append("ok")
            except Conflict:
                results.append("conflicto")

    threads = [threading.Thread(target=pedir) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["conflicto"] * (n - 1) + ["ok"]
    assert db.query(Bloqueo).filter_by(estado=BloqueoEstado.ACTIVO).count() == 1


# ---------------------------------------------------------------- vencimientos


def vencer(db, bloqueo) -> None:
    """Hace que una reserva provisional haya vencido hace un minuto."""
    db.execute(
        text("UPDATE bloqueos SET vence_en = now() - interval '1 minute' WHERE id = :id"),
        {"id": bloqueo.id},
    )
    db.commit()
    db.expire_all()


def test_la_solicitud_vence_a_los_20_minutos(db, equipo, user) -> None:
    hold = disponibilidad.place_hold(db, equipo, h(1), h(3), user)
    assert hold.tipo == BloqueoTipo.SOLICITUD
    minutos = (hold.vence_en - datetime.now(UTC)).total_seconds() / 60
    assert 19 < minutos <= 20
    assert not disponibilidad.is_free(db, equipo, h(1), h(3))


def test_una_solicitud_vencida_libera_el_equipo_sin_ningun_proceso_aparte(db, equipo, user) -> None:
    hold = disponibilidad.place_hold(db, equipo, h(1), h(3), user)
    vencer(db, hold)
    # Las lecturas ya lo ven libre aunque el estado siga «activo» en la tabla...
    assert hold.estado == BloqueoEstado.ACTIVO
    assert disponibilidad.is_free(db, equipo, h(1), h(3))
    assert disponibilidad.occupied_ids(db, [equipo.id], h(1), h(3)) == set()
    # ...y quien reserva después puede hacerlo: el vencido se marca como expirado al insertar.
    otro = disponibilidad.place_hold(db, equipo, h(2), h(4), user)
    db.refresh(hold)
    assert hold.estado == BloqueoEstado.EXPIRADO and otro.estado == BloqueoEstado.ACTIVO


def test_expire_holds_cuenta_y_es_idempotente(db, equipo, user) -> None:
    hold = disponibilidad.place_hold(db, equipo, h(1), h(2), user)
    put_block(db, equipo, user, 5, 6)  # no vence: no debe tocarse
    assert disponibilidad.expire_holds(db) == 0
    vencer(db, hold)
    assert disponibilidad.expire_holds(db) == 1
    db.commit()
    assert disponibilidad.expire_holds(db) == 0
    assert db.query(Bloqueo).filter_by(estado=BloqueoEstado.EXPIRADO).count() == 1


def test_el_comando_expire_holds(db, equipo, user, capsys, monkeypatch) -> None:
    hold = disponibilidad.place_hold(db, equipo, h(1), h(2), user)
    vencer(db, hold)
    monkeypatch.setattr("sys.argv", ["app.cli", "expire-holds"])
    cli.main()
    assert "1 reserva(s) vencida(s)" in capsys.readouterr().out
    db.refresh(hold)
    assert hold.estado == BloqueoEstado.EXPIRADO


# ---------------------------------------------------------------- ciclo de vida


def test_de_solicitud_a_apartado_a_renta(db, equipo, user) -> None:
    hold = disponibilidad.place_hold(db, equipo, h(1), h(9), user)
    disponibilidad.promote_to_apartado(db, hold)
    assert hold.tipo == BloqueoTipo.APARTADO
    horas = (hold.vence_en - datetime.now(UTC)).total_seconds() / 3600
    assert 2.9 < horas <= 3  # 3 horas para cumplir requisitos y pagar el anticipo

    disponibilidad.confirm_rental(db, hold)
    assert hold.tipo == BloqueoTipo.RENTA and hold.vence_en is None
    assert not disponibilidad.is_free(db, equipo, h(2), h(3))


def test_las_transiciones_respetan_el_orden(db, equipo, user) -> None:
    hold = disponibilidad.place_hold(db, equipo, h(1), h(2), user)
    with pytest.raises(Conflict):  # no se puede confirmar sin apartar primero
        disponibilidad.confirm_rental(db, hold)
    disponibilidad.promote_to_apartado(db, hold)
    with pytest.raises(Conflict):  # ni apartar dos veces
        disponibilidad.promote_to_apartado(db, hold)


def test_una_reserva_vencida_no_se_puede_promover(db, equipo, user) -> None:
    hold = disponibilidad.place_hold(db, equipo, h(1), h(2), user)
    vencer(db, hold)
    with pytest.raises(Conflict, match="venció"):
        disponibilidad.promote_to_apartado(db, hold)
    assert hold.estado == BloqueoEstado.EXPIRADO


def test_un_apartado_vencido_no_se_puede_confirmar(db, equipo, user) -> None:
    hold = disponibilidad.place_hold(db, equipo, h(1), h(2), user)
    disponibilidad.promote_to_apartado(db, hold)
    vencer(db, hold)
    with pytest.raises(Conflict, match="venció"):
        disponibilidad.confirm_rental(db, hold)


def test_liberar_deja_el_equipo_libre_y_no_se_repite(db, equipo, user) -> None:
    hold = disponibilidad.place_hold(db, equipo, h(1), h(2), user)
    disponibilidad.release(db, hold)
    assert disponibilidad.is_free(db, equipo, h(1), h(2))
    with pytest.raises(Conflict):
        disponibilidad.release(db, hold)


def test_un_equipo_en_mantenimiento_o_baja_no_se_reserva(db, equipo, user) -> None:
    for status in (EquipoStatus.MANTENIMIENTO, EquipoStatus.BAJA):
        equipo.status = status
        db.commit()
        assert not disponibilidad.is_free(db, equipo, h(1), h(2))
        with pytest.raises(Conflict):
            disponibilidad.place_hold(db, equipo, h(1), h(2), user)


# ---------------------------------------------------------------- situación actual


def test_estado_actual_de_cada_tipo_de_bloqueo(db, make_equipo, user) -> None:
    def nuevo():
        return db.get(Equipo, uuid.UUID(make_equipo()["id"]))

    libre, con_renta, con_hold, en_servicio, apartado_manual, futuro, mant, baja = (
        nuevo() for _ in range(8)
    )
    r = disponibilidad.place_hold(db, con_renta, h(-1), h(5), user)
    disponibilidad.promote_to_apartado(db, r)
    disponibilidad.confirm_rental(db, r)
    disponibilidad.place_hold(db, con_hold, h(-1), h(5), user)
    put_block(db, en_servicio, user, -1, 5, BloqueoTipo.MANTENIMIENTO)
    put_block(db, apartado_manual, user, -1, 5, BloqueoTipo.MANUAL)
    put_block(db, futuro, user, 2, 5)  # aún no empieza
    mant.status = EquipoStatus.MANTENIMIENTO
    baja.status = EquipoStatus.BAJA
    db.commit()

    todos = [libre, con_renta, con_hold, en_servicio, apartado_manual, futuro, mant, baja]
    estados = disponibilidad.estado_actual(db, todos)
    assert [estados[e.id] for e in todos] == [
        EstadoActual.LIBRE,
        EstadoActual.RENTADO,
        EstadoActual.BLOQUEADO,
        EstadoActual.MANTENIMIENTO,
        EstadoActual.BLOQUEADO,
        EstadoActual.LIBRE,
        EstadoActual.MANTENIMIENTO,
        EstadoActual.BAJA,
    ]


def test_una_reserva_vencida_no_cuenta_en_el_estado_actual(db, equipo, user) -> None:
    hold = disponibilidad.place_hold(db, equipo, h(-1), h(5), user)
    assert disponibilidad.estado_actual(db, [equipo])[equipo.id] == EstadoActual.BLOQUEADO
    vencer(db, hold)
    assert disponibilidad.estado_actual(db, [equipo])[equipo.id] == EstadoActual.LIBRE


def test_occupied_ids_con_lista_vacia(db) -> None:
    assert disponibilidad.occupied_ids(db, [], h(0), h(1)) == set()


# ---------------------------------------------------------------- consulta de periodos


def test_parse_window() -> None:
    assert disponibilidad.parse_window(None, None) is None
    assert disponibilidad.parse_window(h(0), h(1)) == (h(0), h(1))
    with pytest.raises(InvalidInput, match="juntos|desde y hasta"):
        disponibilidad.parse_window(h(0), None)
    with pytest.raises(InvalidInput, match="posterior"):
        disponibilidad.parse_window(h(2), h(1))
    with pytest.raises(InvalidInput, match="366"):
        disponibilidad.parse_window(h(0), h(0) + timedelta(days=400))
