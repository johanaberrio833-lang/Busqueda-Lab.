"""Pruebas sin conexión: las fuentes leen respuestas simuladas guardadas en tests/fixtures.

Ejecutar desde la raíz del repositorio:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(RAIZ / "scripts"))

import buscar_ofertas  # noqa: E402
from rastreador import red  # noqa: E402
from rastreador.perfiles import cargar_archivo  # noqa: E402
from rastreador.scoring import evaluar  # noqa: E402
from rastreador.texto import contiene, normalizar  # noqa: E402

PAGINAS = {
    "https://bogota.gov.co/en/taxonomy/term/117": "bogota_ofertas.html",
    "https://bogota.gov.co/portaldelasoportunidades": "bogota_portal.html",
}


def texto_simulado(url, cabeceras=None):
    if url in PAGINAS:
        return (FIX / PAGINAS[url]).read_text(encoding="utf-8")
    if url.startswith("https://bogota.gov.co/"):
        relevante = "contractual" in url or "presupuestal" in url
        return (FIX / ("detalle_contractual.html" if relevante else "detalle_general.html")).read_text(encoding="utf-8")
    raise red.ErrorRed(f"sin simulación para {url}")


def post_simulado(url, cuerpo, cabeceras=None):
    assert "appname=" in url
    if cuerpo.get("offset", 0) > 0:
        return {"data": []}
    return json.loads((FIX / "reliefweb_jobs.json").read_text(encoding="utf-8"))


class PruebasTexto(unittest.TestCase):
    def test_normaliza_tildes_y_signos(self):
        self.assertEqual(normalizar("Gestión  CONTRACTUAL – SECOP II"), "gestion contractual secop ii")

    def test_contiene_palabra_completa(self):
        t = normalizar("Apoyo poscontractual y liquidación")
        self.assertTrue(contiene(t, "poscontractual"))
        self.assertFalse(contiene(t, "contractual"))


class PruebasScoring(unittest.TestCase):
    def setUp(self):
        self.perfil = cargar_archivo(RAIZ / "config" / "perfiles" / "contratacion-publica.json")

    def test_oferta_ideal_puntua_alto(self):
        r, _ = evaluar({"titulo": "Profesional de apoyo a la gestión contractual",
                        "descripcion": "Estudios previos, estudios de mercado y supervisión de contratos en SECOP II",
                        "ubicacion": "Bogotá D.C."}, self.perfil)
        self.assertGreaterEqual(r["puntaje"], 90)

    def test_cooperacion_y_rediseno_puntuan(self):
        r1, _ = evaluar({"titulo": "Profesional de apoyo a la implementación de proyectos de cooperación",
                         "descripcion": "Seguimiento a convenios de cooperación internacional y socios implementadores",
                         "ubicacion": "Bogotá"}, self.perfil)
        r2, _ = evaluar({"titulo": "Profesional de fortalecimiento institucional",
                         "descripcion": "Rediseño institucional: estudio técnico, cargas de trabajo y manual específico de funciones",
                         "ubicacion": "Bogotá"}, self.perfil)
        self.assertGreaterEqual(r1["puntaje"], 70)
        self.assertGreaterEqual(r2["puntaje"], 90)

    def test_exclusion_descarta(self):
        r, motivo = evaluar({"titulo": "Conductor para contratación estatal", "ubicacion": "Bogotá"}, self.perfil)
        self.assertIsNone(r)
        self.assertIn("exclusión", motivo)

    def test_penalizacion_resta_sin_descartar(self):
        base = {"titulo": "Profesional de contratación", "descripcion": "Gestión contractual y estudios previos",
                "ubicacion": "Bogotá"}
        r1, _ = evaluar(base, self.perfil)
        r2, _ = evaluar({**base, "descripcion": base["descripcion"] + ". Requiere título de abogado"}, self.perfil)
        self.assertLess(r2["puntaje"], r1["puntaje"])

    def test_ciudad_fuera_de_lista_se_descarta(self):
        r, motivo = evaluar({"titulo": "Procurement Associate", "descripcion": "public procurement",
                             "ubicacion": "Cali, Colombia"}, self.perfil)
        self.assertIsNone(r)
        self.assertIn("ubicación", motivo)

    def test_solo_pais_se_acepta(self):
        r, _ = evaluar({"titulo": "Profesional de contratación", "descripcion": "contratación estatal SECOP II",
                        "ubicacion": "Colombia"}, self.perfil)
        self.assertIsNotNone(r)


class PruebaFlujoCompleto(unittest.TestCase):
    def test_busqueda_deduplicacion_y_dominios(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            shutil.copytree(RAIZ / "config", raiz / "config")
            salida = raiz / "salida.txt"
            env = {"RELIEFWEB_APPNAME": "prueba", "GITHUB_OUTPUT": str(salida)}
            with mock.patch.dict(os.environ, env), \
                    mock.patch.object(red, "texto", side_effect=texto_simulado), \
                    mock.patch.object(red, "json_post", side_effect=post_simulado), \
                    mock.patch.object(sys, "argv", ["buscar_ofertas.py", "--raiz", str(raiz)]):
                self.assertEqual(buscar_ofertas.main(), 0)
                datos = json.loads((raiz / "docs" / "data" / "ofertas.json").read_text(encoding="utf-8"))
                primera = len(datos["ofertas"])
                self.assertGreater(primera, 0)
                self.assertIn("nuevas=", salida.read_text())
                # Solo dominios oficiales
                self.assertTrue(all(".gov.co" in o["url"] or "reliefweb.int" in o["url"] for o in datos["ofertas"]))
                # El duplicado entre fuentes se fusiona
                titulos = [o["titulo"] for o in datos["ofertas"]]
                self.assertEqual(len(titulos), len(set(titulos)))
                # Segunda ejecución: nada nuevo
                salida.write_text("")
                self.assertEqual(buscar_ofertas.main(), 0)
                self.assertIn("nuevas=0", salida.read_text())
                datos2 = json.loads((raiz / "docs" / "data" / "ofertas.json").read_text(encoding="utf-8"))
                self.assertEqual(len(datos2["ofertas"]), primera)

    def test_fuente_sin_clave_se_omite(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            shutil.copytree(RAIZ / "config", raiz / "config")
            env = {k: v for k, v in os.environ.items() if k != "RELIEFWEB_APPNAME"}
            with mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(red, "texto", side_effect=texto_simulado), \
                    mock.patch.object(sys, "argv", ["buscar_ofertas.py", "--raiz", str(raiz)]):
                self.assertEqual(buscar_ofertas.main(), 0)
                datos = json.loads((raiz / "docs" / "data" / "ofertas.json").read_text(encoding="utf-8"))
                self.assertTrue(datos["estado_fuentes"]["reliefweb"].get("omitida"))


if __name__ == "__main__":
    unittest.main()
