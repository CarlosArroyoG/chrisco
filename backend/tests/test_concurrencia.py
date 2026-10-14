"""El límite de usuarios por empresa debe resistir invitaciones simultáneas."""

import threading

from app.core.errors import Conflict
from app.db.session import SessionLocal
from app.models.empresa import Empresa
from app.services import accounts, empresas
from tests.conftest import COMPANY


def test_dos_invitaciones_simultaneas_no_pasan_del_maximo(
    approved_owner: dict[str, str], db, client
) -> None:
    empresa = db.query(Empresa).one()
    owner = accounts.get_by_email(db, COMPANY["email"])
    empresas.invite_user(db, empresa.id, owner, "uno@constructora-prueba.com", "Uno")  # 2 de 3

    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def invite(email: str) -> None:
        with SessionLocal() as session:
            barrier.wait()
            try:
                empresas.invite_user(session, empresa.id, owner, email, "Compañero")
                outcomes.append("ok")
            except Conflict:
                outcomes.append("conflicto")

    threads = [
        threading.Thread(target=invite, args=(f"{n}@constructora-prueba.com",)) for n in ("a", "b")
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(outcomes) == ["conflicto", "ok"]
    db.expire_all()
    assert empresas.active_user_count(db, empresa.id) == 3
