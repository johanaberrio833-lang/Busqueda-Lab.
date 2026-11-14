"""Cliente HTTP mínimo (solo biblioteca estándar) con reintentos."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

AGENTE = "RastreadorVacantesInstitucionales/1.0 (+https://github.com; uso personal, consultas diarias)"
TIEMPO_ESPERA = 30


class ErrorRed(RuntimeError):
    pass


def _solicitar(url: str, datos: bytes | None = None, cabeceras: dict | None = None,
               reintentos: int = 2) -> bytes:
    cab = {"User-Agent": AGENTE, "Accept": "*/*", "Accept-Language": "es-CO,es;q=0.9,en;q=0.8"}
    cab.update(cabeceras or {})
    ultimo_error: Exception | None = None
    for intento in range(reintentos + 1):
        try:
            req = urllib.request.Request(url, data=datos, headers=cab, method="POST" if datos else "GET")
            with urllib.request.urlopen(req, timeout=TIEMPO_ESPERA) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            cuerpo = e.read()[:300].decode("utf-8", "replace")
            ultimo_error = ErrorRed(f"HTTP {e.code} en {url}: {cuerpo}")
            if e.code < 500 and e.code != 429:
                break  # errores del cliente no mejoran reintentando
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            ultimo_error = ErrorRed(f"No se pudo conectar con {url}: {e}")
        time.sleep(2 * (intento + 1))
    raise ultimo_error or ErrorRed(f"Fallo desconocido en {url}")


def texto(url: str, cabeceras: dict | None = None) -> str:
    crudo = _solicitar(url, cabeceras=cabeceras)
    for codificacion in ("utf-8", "latin-1"):
        try:
            return crudo.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return crudo.decode("utf-8", "replace")


def json_get(url: str, parametros: dict | None = None, cabeceras: dict | None = None):
    if parametros:
        url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(parametros, doseq=True)}"
    return json.loads(_solicitar(url, cabeceras={"Accept": "application/json", **(cabeceras or {})}))


def json_post(url: str, cuerpo: dict, cabeceras: dict | None = None):
    datos = json.dumps(cuerpo).encode("utf-8")
    cab = {"Content-Type": "application/json", "Accept": "application/json", **(cabeceras or {})}
    return json.loads(_solicitar(url, datos=datos, cabeceras=cab))
