#!/usr/bin/env python3
"""Valida perfiles y prueba cómo puntuaría una oferta.

Ejemplos:
  python scripts/validar_perfil.py                                   # valida todos los perfiles
  python scripts/validar_perfil.py config/perfiles/trabajo-social.json
  python scripts/validar_perfil.py config/perfiles/contratacion-publica.json \\
      --titulo "Profesional de apoyo a la gestión contractual" \\
      --texto "Elaborar estudios previos y apoyar la supervisión en SECOP II" --ubicacion "Bogotá"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rastreador.perfiles import PerfilInvalido, cargar_archivo  # noqa: E402
from rastreador.scoring import evaluar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivos", nargs="*", type=Path)
    ap.add_argument("--titulo", help="título de una oferta de prueba")
    ap.add_argument("--texto", default="", help="descripción de la oferta de prueba")
    ap.add_argument("--ubicacion", default="", help="ubicación de la oferta de prueba")
    args = ap.parse_args()

    archivos = args.archivos or sorted(p for p in (RAIZ / "config" / "perfiles").glob("*.json")
                                       if not p.name.startswith("_"))
    hubo_error = False
    for ruta in archivos:
        try:
            perfil = cargar_archivo(ruta)
        except PerfilInvalido as e:
            print(f"✗ {e}")
            hubo_error = True
            continue
        estado = "activo" if perfil["activo"] else "inactivo"
        print(f"✓ {ruta.name}: '{perfil['nombre']}' ({estado}) – {len(perfil['roles_objetivo'])} roles, "
              f"{len(perfil['palabras_clave_principales']['terminos'])} principales, "
              f"{len(perfil['palabras_clave_secundarias']['terminos'])} secundarias, "
              f"{len(perfil['palabras_exclusion'])} exclusiones")
        if args.titulo:
            oferta = {"titulo": args.titulo, "descripcion": args.texto, "ubicacion": args.ubicacion}
            resultado, motivo = evaluar(oferta, perfil)
            if resultado:
                print(f"   → Afinidad {resultado['puntaje']}% | rol: {resultado['rol'] or '—'} | "
                      f"coincidencias: {', '.join(resultado['coincidencias']) or '—'}"
                      + (f" | penalizaciones: {', '.join(resultado['penalizaciones'])}"
                         if resultado['penalizaciones'] else ""))
            else:
                print(f"   → Descartada ({motivo})")
    return 1 if hubo_error else 0


if __name__ == "__main__":
    sys.exit(main())
