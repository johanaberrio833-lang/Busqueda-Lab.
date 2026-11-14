"""Lectura y escritura de docs/data/ofertas.json y data/vistos.json, con deduplicación."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .texto import normalizar


def ahora_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def id_oferta(fuente: str, id_externo: str) -> str:
    return hashlib.sha1(f"{fuente}|{id_externo}".encode("utf-8")).hexdigest()[:16]


def clave_contenido(oferta: dict) -> str:
    """Detecta la misma vacante publicada en dos fuentes."""
    return f"{normalizar(oferta.get('titulo'))}|{normalizar(oferta.get('organizacion'))}"


def _leer_json(ruta: Path, por_defecto):
    if not ruta.exists():
        return por_defecto
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return por_defecto


def _escribir_json(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class Almacen:
    def __init__(self, ruta_ofertas: Path, ruta_vistos: Path, firma_perfiles: str):
        self.ruta_ofertas = ruta_ofertas
        self.ruta_vistos = ruta_vistos
        datos = _leer_json(ruta_ofertas, {})
        self.ofertas: dict[str, dict] = {o["id"]: o for o in datos.get("ofertas", [])}
        self.claves = {clave_contenido(o): o["id"] for o in self.ofertas.values()}
        vistos = _leer_json(ruta_vistos, {})
        self.perfiles_cambiaron = vistos.get("firma_perfiles") != firma_perfiles
        self.vistos: dict[str, str] = {} if self.perfiles_cambiaron else vistos.get("ids", {})
        self.firma = firma_perfiles
        self.nuevas: list[str] = []
        self.actualizadas = 0

    def ya_visto(self, oid: str) -> bool:
        return oid in self.vistos or oid in self.ofertas

    def marcar_visto(self, oid: str) -> None:
        self.vistos.setdefault(oid, ahora_iso()[:10])

    def registrar(self, oferta: dict) -> str:
        """Guarda una oferta que pasó el filtro. Devuelve 'nueva', 'actualizada' o 'duplicada'."""
        oid = oferta["id"]
        if oid in self.ofertas:
            previa = self.ofertas[oid]
            if previa.get("afinidad") != oferta["afinidad"]:
                previa["afinidad"] = oferta["afinidad"]
                self.actualizadas += 1
                return "actualizada"
            return "duplicada"
        clave = clave_contenido(oferta)
        if clave in self.claves:
            otra = self.ofertas[self.claves[clave]]
            otra.setdefault("tambien_en", [])
            if oferta["url"] not in otra["tambien_en"] and oferta["url"] != otra["url"]:
                otra["tambien_en"].append(oferta["url"])
            return "duplicada"
        oferta["fecha_detectada"] = ahora_iso()
        self.ofertas[oid] = oferta
        self.claves[clave] = oid
        self.nuevas.append(oid)
        return "nueva"

    def retirar(self, oid: str) -> None:
        oferta = self.ofertas.pop(oid, None)
        if oferta:
            self.claves.pop(clave_contenido(oferta), None)
            self.actualizadas += 1

    def depurar(self, dias_retencion: int, max_ofertas: int) -> int:
        limite = (datetime.now(timezone.utc) - timedelta(days=dias_retencion)).isoformat()
        antes = len(self.ofertas)
        conservar = [o for o in self.ofertas.values() if o.get("fecha_detectada", "") >= limite]
        conservar.sort(key=lambda o: o.get("fecha_detectada", ""), reverse=True)
        self.ofertas = {o["id"]: o for o in conservar[:max_ofertas]}
        limite_vistos = (datetime.now(timezone.utc) - timedelta(days=dias_retencion * 3)).date().isoformat()
        self.vistos = {k: v for k, v in self.vistos.items() if v >= limite_vistos}
        return antes - len(self.ofertas)

    def guardar(self, perfiles: list[dict], estado_fuentes: dict) -> None:
        ofertas = sorted(self.ofertas.values(),
                         key=lambda o: (o.get("fecha_detectada", ""), o.get("fecha_publicacion") or ""),
                         reverse=True)
        _escribir_json(self.ruta_ofertas, {
            "actualizado": ahora_iso(),
            "perfiles": [{"id": p["id"], "nombre": p["nombre"]} for p in perfiles],
            "estado_fuentes": estado_fuentes,
            "total": len(ofertas),
            "ofertas": ofertas,
        })
        _escribir_json(self.ruta_vistos, {"firma_perfiles": self.firma, "ids": self.vistos})
