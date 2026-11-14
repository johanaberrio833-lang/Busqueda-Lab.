#!/usr/bin/env python3
"""Busca vacantes en fuentes institucionales, las puntúa contra cada perfil y actualiza
docs/data/ofertas.json.

Uso:
  python scripts/buscar_ofertas.py              # ejecución normal
  python scripts/buscar_ofertas.py --simulacion # muestra resultados sin guardar
  python scripts/buscar_ofertas.py --fuente rss # solo una fuente

Solo usa la biblioteca estándar de Python 3.10+.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rastreador import perfiles as mod_perfiles  # noqa: E402
from rastreador.almacen import Almacen, ahora_iso, id_oferta  # noqa: E402
from rastreador.fuentes import REGISTRO, Contexto, FuenteNoConfigurada  # noqa: E402
from rastreador.scoring import evaluar  # noqa: E402
from rastreador.texto import recortar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def dominio_permitido(url: str, sufijos: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == s or host.endswith("." + s) for s in sufijos)


def anotar(mensaje: str, nivel: str = "notice") -> None:
    """Muestra el mensaje en consola y como anotación visible en GitHub Actions."""
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::{nivel}::{mensaje}")
    else:
        print(f"[{nivel}] {mensaje}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", type=Path, default=RAIZ, help="carpeta raíz del repositorio")
    ap.add_argument("--simulacion", action="store_true", help="no escribe archivos")
    ap.add_argument("--fuente", help="ejecuta solo esta fuente")
    args = ap.parse_args()

    raiz: Path = args.raiz
    config = json.loads((raiz / "config" / "fuentes.json").read_text(encoding="utf-8"))
    general = config.get("general", {})
    sufijos = [s.lower().lstrip(".") for s in general.get("dominios_oficiales", [])]

    try:
        perfiles = mod_perfiles.cargar_activos(raiz / "config" / "perfiles")
    except mod_perfiles.PerfilInvalido as e:
        anotar(f"Perfil inválido: {e}", "error")
        return 1
    if not perfiles:
        anotar("No hay perfiles activos en config/perfiles/.", "error")
        return 1

    almacen = Almacen(raiz / "docs" / "data" / "ofertas.json", raiz / "data" / "vistos.json",
                      mod_perfiles.firma(perfiles))
    if almacen.perfiles_cambiaron:
        anotar("Los perfiles cambiaron: se reevaluarán todas las ofertas encontradas.")

    terminos = list(dict.fromkeys(t for p in perfiles for t in p.get("terminos_busqueda", [])))
    estado_fuentes: dict[str, dict] = {}
    descartes: dict[str, int] = {}

    for nombre, conf in config.get("fuentes", {}).items():
        if args.fuente and nombre != args.fuente:
            continue
        if not conf.get("activa", False):
            continue
        funcion = REGISTRO.get(nombre)
        if not funcion:
            anotar(f"Fuente '{nombre}' no está registrada en scripts/rastreador/fuentes.", "warning")
            continue

        ctx = Contexto(terminos=terminos,
                       ya_visto=lambda f, ide: almacen.ya_visto(id_oferta(f, ide)))
        registro = {"ok": True, "fecha": ahora_iso(), "obtenidas": 0, "relevantes": 0, "nuevas": 0}
        try:
            crudas = funcion(conf, ctx)
        except FuenteNoConfigurada as e:
            estado_fuentes[nombre] = {**registro, "ok": False, "omitida": True, "mensaje": str(e)}
            anotar(f"{nombre}: omitida. {e}")
            continue
        except Exception as e:  # una fuente caída no detiene las demás
            estado_fuentes[nombre] = {**registro, "ok": False, "mensaje": f"{type(e).__name__}: {e}"[:300]}
            anotar(f"{nombre}: falló. {e}", "warning")
            continue

        registro["obtenidas"] = len(crudas)
        for cruda in crudas:
            if not cruda.get("titulo") or not cruda.get("url"):
                continue
            oid = id_oferta(nombre, cruda["id_externo"])
            if oid in almacen.ofertas:
                if not almacen.perfiles_cambiaron:
                    continue  # ya está en el tablero
                if not cruda.get("descripcion"):  # reevaluar con lo que ya se había leído
                    cruda["descripcion"] = almacen.ofertas[oid].get("resumen", "")
            elif oid in almacen.vistos:
                continue  # ya se evaluó y descartó antes con los mismos perfiles
            almacen.marcar_visto(oid)

            if sufijos and not dominio_permitido(cruda["url"], sufijos):
                descartes["dominio no oficial"] = descartes.get("dominio no oficial", 0) + 1
                continue

            afinidad = {}
            for perfil in perfiles:
                resultado, motivo = evaluar(cruda, perfil)
                if resultado:
                    afinidad[perfil["id"]] = resultado
                else:
                    clave = motivo.split(":")[0]
                    descartes[clave] = descartes.get(clave, 0) + 1
            if not afinidad:
                almacen.retirar(oid)  # si ya estaba y con los perfiles nuevos no aplica
                continue

            registro["relevantes"] += 1
            oferta = {
                "id": oid,
                "fuente": nombre,
                "fuente_detalle": cruda.get("fuente_detalle", ""),
                "tipo": cruda.get("tipo", "vacante"),
                "titulo": cruda["titulo"],
                "organizacion": cruda.get("organizacion", ""),
                "ubicacion": cruda.get("ubicacion", ""),
                "url": cruda["url"],
                "fecha_publicacion": cruda.get("fecha_publicacion"),
                "fecha_cierre": cruda.get("fecha_cierre"),
                "resumen": recortar(cruda.get("descripcion", ""), 600),
                "afinidad": afinidad,
            }
            if almacen.registrar(oferta) == "nueva":
                registro["nuevas"] += 1

        if ctx.avisos:
            registro["avisos"] = ctx.avisos[:20]
            for aviso in ctx.avisos[:10]:
                anotar(f"{nombre}: {aviso}", "warning")
        estado_fuentes[nombre] = registro
        print(f"{nombre}: {registro['obtenidas']} leídas, {registro['relevantes']} relevantes, "
              f"{registro['nuevas']} nuevas")

    eliminadas = almacen.depurar(int(general.get("dias_retencion", 60)), int(general.get("max_ofertas", 1500)))
    nuevas = len(almacen.nuevas)
    print(f"Total: {nuevas} nuevas, {almacen.actualizadas} con puntaje actualizado, "
          f"{eliminadas} archivadas por antigüedad, {len(almacen.ofertas)} en el tablero.")
    if descartes:
        print("Descartes: " + ", ".join(f"{k}={v}" for k, v in sorted(descartes.items())))

    if args.simulacion:
        for oid in almacen.nuevas[:30]:
            o = almacen.ofertas[oid]
            mejor = max(a["puntaje"] for a in o["afinidad"].values())
            print(f"  {mejor:>3}%  {o['titulo'][:90]}  ({o['organizacion'][:40]})")
        print("Simulación: no se guardó nada.")
    else:
        almacen.guardar(perfiles, estado_fuentes)

    cambios = nuevas + almacen.actualizadas + eliminadas
    salida = os.environ.get("GITHUB_OUTPUT")
    if salida:
        with open(salida, "a", encoding="utf-8") as fh:
            fh.write(f"nuevas={nuevas}\ncambios={cambios}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
