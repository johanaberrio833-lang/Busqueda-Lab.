"""Monitor de páginas oficiales de convocatorias (entidades .gov.co y organismos internacionales).

Lee la página de listado configurada, toma los enlaces cuyo texto o dirección sugieren una
vacante o convocatoria, y trata cada enlace nuevo como una oferta. Opcionalmente abre cada
enlace nuevo para leer su descripción y mejorar el puntaje.

Funciona con páginas que entregan su contenido en el HTML (la mayoría de portales Drupal,
WordPress y Liferay del Estado). No funciona con aplicaciones que cargan todo con JavaScript.
"""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse

from .. import red
from ..texto import contiene, limpiar_html, normalizar, recortar
from .base import Contexto, fecha_iso

PALABRAS_ENLACE_POR_DEFECTO = [
    "convocatoria", "convocatorias", "vacante", "vacantes", "empleo", "empleos", "contratista",
    "contratistas", "prestacion de servicios", "hoja de vida", "hojas de vida", "trabaje con nosotros",
    "oportunidad laboral", "oportunidades laborales", "oferta laboral", "ofertas laborales",
    "proceso de seleccion", "banco de hojas de vida", "talento", "consultor", "consultoria",
    "job", "jobs", "vacancy", "vacancies", "consultancy", "call for", "terms of reference",
]
EXTENSIONES_IGNORADAS = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".mp4", ".mp3")


class _Enlaces(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.enlaces: list[tuple[str, str]] = []
        self._href: str | None = None
        self._texto: list[str] = []
        self._title = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            a = dict(attrs)
            self._href = a.get("href")
            self._title = a.get("title") or a.get("aria-label") or ""
            self._texto = []

    def handle_data(self, data):
        if self._href is not None:
            self._texto.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            texto = " ".join("".join(self._texto).split()) or self._title.strip()
            self.enlaces.append((self._href, texto))
            self._href = None


def _dominio_base(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _descripcion_de(url: str) -> str:
    html = red.texto(url)
    meta = re.search(r'<meta[^>]+(?:name|property)=["\'](?:og:)?description["\'][^>]+content=["\']([^"\']+)',
                     html, re.I)
    cuerpo = re.search(r"<(main|article)[^>]*>(.*?)</\1>", html, re.S | re.I)
    texto = limpiar_html(cuerpo.group(2) if cuerpo else html)
    return recortar(((meta.group(1) + ". ") if meta else "") + texto, 3000)


def buscar(config: dict, ctx: Contexto) -> list[dict]:
    palabras_globales = config.get("palabras_enlace") or PALABRAS_ENLACE_POR_DEFECTO
    max_detalles = int(config.get("max_detalles_por_pagina", 10))
    ofertas: list[dict] = []

    for pagina in config.get("paginas", []):
        if not pagina.get("activa", True):
            continue
        url_pagina = pagina["url"]
        try:
            html = red.texto(url_pagina)
        except red.ErrorRed as e:
            ctx.avisar(f"{pagina.get('nombre', url_pagina)}: {e}")
            continue

        parser = _Enlaces()
        parser.feed(html)
        dominio = _dominio_base(url_pagina)
        palabras = pagina.get("palabras_enlace") or palabras_globales
        patron = re.compile(pagina["patron_url"]) if pagina.get("patron_url") else None
        vistos_aqui: set[str] = set()
        detalles = 0
        encontrados = 0

        for href, texto in parser.enlaces:
            if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            url = urldefrag(urljoin(url_pagina, href))[0]
            if url in vistos_aqui or url.rstrip("/") == url_pagina.rstrip("/"):
                continue
            if url.lower().endswith(EXTENSIONES_IGNORADAS):
                continue
            if not pagina.get("permitir_otros_dominios") and not _dominio_base(url).endswith(dominio):
                continue
            if patron and not patron.search(url):
                continue
            if len(texto) < int(pagina.get("min_caracteres_titulo", 15)):
                continue
            ruta_n = normalizar(urlparse(url).path)
            texto_n = normalizar(texto)
            if not pagina.get("todas_las_entradas") and not any(
                    contiene(texto_n, p) or contiene(ruta_n, p) for p in palabras):
                continue
            vistos_aqui.add(url)
            encontrados += 1

            id_externo = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
            descripcion = ""
            if (pagina.get("leer_detalle", True) and detalles < max_detalles
                    and not ctx.ya_visto("paginas_oficiales", id_externo)
                    and not url.lower().endswith(".pdf")):
                detalles += 1
                try:
                    descripcion = _descripcion_de(url)
                except red.ErrorRed as e:
                    ctx.avisar(f"No se pudo leer el detalle de {url}: {e}")

            ofertas.append({
                "id_externo": id_externo,
                "titulo": texto,
                "organizacion": pagina.get("organizacion", pagina.get("nombre", dominio)),
                "ubicacion": pagina.get("ubicacion", "Colombia"),
                "url": url,
                "fecha_publicacion": fecha_iso(url) if re.search(r"20\d\d-\d\d-\d\d", url) else None,
                "descripcion": descripcion,
                "tipo": pagina.get("tipo", "convocatoria"),
                "fuente_detalle": pagina.get("nombre", dominio),
            })
        if encontrados == 0:
            ctx.avisar(f"{pagina.get('nombre', url_pagina)}: no se encontraron enlaces de convocatorias "
                       "(revise la URL o si la página carga con JavaScript).")
    return ofertas
