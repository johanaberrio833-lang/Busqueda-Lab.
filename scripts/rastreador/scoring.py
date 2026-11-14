"""Puntaje de afinidad (0-100) de una oferta frente a un perfil."""

from __future__ import annotations

from .texto import contiene, normalizar

PALABRAS_REMOTO = ("remoto", "remote", "teletrabajo", "trabajo en casa", "home office", "100 virtual")
PALABRAS_HIBRIDO = ("hibrido", "hybrid", "semipresencial")


def detectar_modalidad(oferta: dict, texto_n: str) -> str | None:
    declarada = normalizar(oferta.get("modalidad"))
    if declarada:
        if "hibrid" in declarada:
            return "hibrido"
        if "remot" in declarada or "virtual" in declarada:
            return "remoto"
        if "presencial" in declarada or "onsite" in declarada:
            return "presencial"
    if any(contiene(texto_n, p) for p in PALABRAS_HIBRIDO):
        return "hibrido"
    if any(contiene(texto_n, p) for p in PALABRAS_REMOTO):
        return "remoto"
    return None


def evaluar(oferta: dict, perfil: dict) -> tuple[dict | None, str]:
    """Devuelve (resultado, motivo). resultado es None si la oferta se descarta."""
    titulo_n = normalizar(oferta.get("titulo"))
    texto_n = normalizar(" ".join(str(oferta.get(k) or "") for k in
                                  ("titulo", "organizacion", "ubicacion", "descripcion", "resumen")))
    sc = perfil["scoring"]

    for termino in perfil.get("palabras_exclusion", []):
        if contiene(texto_n, termino):
            return None, f"exclusión: «{termino}»"

    # Ubicación y modalidad
    um = perfil.get("ubicacion_modalidad", {})
    modalidad = detectar_modalidad(oferta, texto_n)
    aceptadas = [normalizar(m) for m in um.get("modalidades_aceptadas", [])]
    if modalidad and aceptadas and modalidad not in aceptadas:
        return None, f"modalidad no aceptada: {modalidad}"

    ubic_n = normalizar(oferta.get("ubicacion"))
    preferidas = um.get("ciudades_preferidas", [])
    lugares_ok = [um.get("pais", "")] + preferidas + um.get("ciudades_aceptadas", [])
    lugares_ok = [x for x in lugares_ok if x]
    bonus = 0
    if ubic_n and lugares_ok:
        ciudades = preferidas + um.get("ciudades_aceptadas", [])
        if um.get("solo_ciudades_listadas") and ciudades and ubic_n != normalizar(um.get("pais")):
            # la oferta nombra una ciudad: debe ser una de las listadas
            en_zona = any(contiene(ubic_n, c) for c in ciudades)
        else:
            en_zona = any(contiene(ubic_n, lugar) for lugar in lugares_ok)
        if not en_zona:
            if not (modalidad == "remoto" and um.get("aceptar_remoto_internacional")):
                return None, f"ubicación fuera de la zona: {oferta.get('ubicacion')}"
        if any(contiene(ubic_n, c) for c in preferidas):
            bonus = sc["puntos_bonus_ciudad_preferida"]

    crudo = bonus
    coincidencias: list[str] = []

    rol = next((r for r in perfil["roles_objetivo"] if contiene(titulo_n, r)), None)
    if rol:
        crudo += sc["puntos_por_rol_en_titulo"]
    else:
        rol = next((r for r in perfil["roles_objetivo"] if contiene(texto_n, r)), None)
        if rol:
            crudo += sc["puntos_por_rol_en_texto"]

    for clave in ("palabras_clave_principales", "palabras_clave_secundarias"):
        bloque = perfil[clave]
        for termino in bloque["terminos"]:
            if contiene(texto_n, termino):
                crudo += bloque["peso"]
                coincidencias.append(termino)

    penalizaciones = [t for t in perfil["palabras_penalizacion"]["terminos"] if contiene(texto_n, t)]
    crudo -= perfil["palabras_penalizacion"]["peso"] * len(penalizaciones)

    puntaje = max(0, min(100, round(crudo / sc["puntaje_crudo_para_100"] * 100)))
    if puntaje < sc["afinidad_minima_para_guardar"]:
        return None, f"afinidad {puntaje}% < mínimo {sc['afinidad_minima_para_guardar']}%"

    return {
        "puntaje": puntaje,
        "rol": rol,
        "coincidencias": coincidencias,
        "penalizaciones": penalizaciones,
        "modalidad": modalidad,
    }, "ok"
