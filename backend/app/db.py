import socket
from urllib.parse import urlparse

from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings


# ──────────────────────────────────────────────────────────────────────────────
# Connexion Neon depuis Railway — IPv6 cassé sur Railway : Neon publie des AAAA
# (IPv6) et libpq tente l'IPv6 en premier → « Network is unreachable ». On force
# donc l'IPv4 en résolvant le hostname nous-mêmes et en passant `hostaddr`
# (l'IP), tout en gardant `host` (le hostname, depuis l'URL) pour le SNI/SSL.
#
# IMPORTANT : on NE passe PAS `options=endpoint=...`. Comme `host` reste le
# hostname complet (…-pooler.…neon.tech), le SNI TLS porte déjà le bon nom de
# projet et le proxy Neon route correctement. Ajouter l'option endpoint crée au
# contraire un conflit : « Inconsistent project name inferred from SNI ».
# ──────────────────────────────────────────────────────────────────────────────


def _resolve_ipv4(host: str, port: int) -> str | None:
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        if infos:
            return infos[0][4][0]
    except OSError:
        pass
    return None


_connect_args: dict = {"connect_timeout": 30}

_parsed = urlparse(settings.DATABASE_URL)
_db_host = _parsed.hostname
_db_port = _parsed.port or 5432

if _db_host and "neon.tech" in _db_host:
    _ipv4 = _resolve_ipv4(_db_host, _db_port)
    if _ipv4:
        _connect_args["hostaddr"] = _ipv4
        print(f"[db] Neon host {_db_host} -> IPv4 {_ipv4} (hostaddr forced)", flush=True)
    else:
        print(f"[db] WARNING: no IPv4 found for {_db_host}", flush=True)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    connect_args=_connect_args,
)


# Filet de sécurité : ré-applique l'IPv4 sur chaque nouvelle connexion physique
# (au cas où l'IP Neon change pendant la vie du process).
@event.listens_for(engine.sync_engine, "do_connect")
def _force_neon_ipv4(dialect, conn_rec, cargs, cparams):
    host = cparams.get("host")
    if host and "neon.tech" in host and "hostaddr" not in cparams:
        ipv4 = _resolve_ipv4(host, cparams.get("port", 5432))
        if ipv4:
            cparams["hostaddr"] = ipv4


AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
