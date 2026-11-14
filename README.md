# Radar de vacantes institucionales

Rastreador diario de vacantes y convocatorias en **fuentes oficiales**: entidades del Estado colombiano (`.gov.co`), organismos de cooperación internacional y agencias de la ONU. Puntúa cada oferta según uno o varios **perfiles anónimos** y las muestra en un tablero web con un **CRM personal** (estados y notas) guardado solo en tu navegador.

```
config/
  fuentes.json              Fuentes activas, páginas a revisar y dominios oficiales permitidos
  perfiles/
    contratacion-publica.json   Perfil inicial (anónimo)
    _plantilla.json             Plantilla para crear perfiles nuevos
scripts/
  buscar_ofertas.py         Busca, puntúa, deduplica y guarda docs/data/ofertas.json
  validar_perfil.py         Valida perfiles y prueba el puntaje de una oferta
  rastreador/               Núcleo (texto, red, perfiles, scoring, almacén, fuentes/)
docs/                       Tablero para GitHub Pages (index.html, style.css, app.js)
  data/ofertas.json         Resultado que lee el tablero
data/vistos.json            Ofertas ya evaluadas (evita repetir trabajo)
tests/                      Pruebas sin conexión con respuestas simuladas
.github/workflows/actualizar.yml   Ejecución diaria 7:00 a. m. (hora Colombia)
```

No necesita instalar dependencias: solo Python 3.10+ (biblioteca estándar).

---

## 1. Puesta en marcha (una sola vez)

1. **Cree un repositorio** en GitHub y suba esta carpeta completa.
   - GitHub Pages gratuito solo publica repositorios **públicos**. Lo publicado será el perfil anónimo y las ofertas encontradas; nunca su hoja de vida ni sus datos (ver *Privacidad*).
2. **Permisos del flujo:** *Settings → Actions → General → Workflow permissions →* **Read and write permissions** → *Save*.
3. **Publicar el tablero:** *Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: `main` / carpeta `/docs`* → *Save*. La dirección queda como `https://SU-USUARIO.github.io/NOMBRE-REPO/`.
4. **ReliefWeb (recomendado):** desde noviembre de 2025 la API de ReliefWeb exige un *appname* aprobado.
   - Solicítelo gratis en la documentación oficial: <https://apidoc.reliefweb.int/> (enlace *Request an appname*). Use un nombre propio, por ejemplo `radar-vacantes-co-SUINICIAL`.
   - Cuando lo aprueben: *Settings → Secrets and variables → Actions → New repository secret* → nombre `RELIEFWEB_APPNAME`, valor: su appname.
   - Sin el secreto, la fuente se omite y las demás siguen funcionando.
5. **Primera ejecución:** pestaña *Actions → Actualizar vacantes → Run workflow*. Revise el resumen y las advertencias.

Desde ahí corre solo todos los días a las 7:00 a. m. y hace *commit* únicamente si hay vacantes nuevas.

> GitHub desactiva los flujos programados de repositorios públicos sin actividad durante 60 días. Si pasa, entre a *Actions* y pulse *Enable workflow*.

## 2. Fuentes

Todas son oficiales. Además, `config/fuentes.json → general.dominios_oficiales` funciona como **lista blanca**: cualquier oferta cuyo enlace no pertenezca a esos dominios (por ejemplo, un portal privado de empleo) se descarta.

| Fuente | Qué cubre | Configuración |
|---|---|---|
| `reliefweb` | Servicio oficial de OCHA (ONU): vacantes en Colombia de agencias ONU, cooperación internacional y organizaciones sociales | Secreto `RELIEFWEB_APPNAME` |
| `paginas_oficiales` | Páginas de convocatorias de entidades `.gov.co` y organismos internacionales. Detecta enlaces nuevos y lee su detalle | Lista `paginas` |
| `rss` | Feeds RSS/Atom oficiales o **alertas de Google** limitadas a sitios oficiales | Lista `feeds` |

### Agregar o activar una página oficial
En `paginas_oficiales.paginas` ya hay entidades listas para activar (ICBF, Prosperidad Social, Unidad para las Víctimas, APC-Colombia, Servicio Civil Distrital, CNSC, Función Pública, DNP). Para cada una:

1. Abra el sitio y ubique la página donde la entidad lista sus convocatorias, contratistas o empleos.
2. Pegue esa URL en `url` y cambie `"activa": true`.
3. Opcional: `patron_url` (expresión regular que deben cumplir los enlaces), `palabras_enlace` (palabras que identifican una convocatoria) o `"todas_las_entradas": true` si todo lo que lista la página son ofertas.

Si la página carga su contenido con JavaScript, el monitor no verá enlaces. En el tablero, en *Estado de las fuentes*, aparecerá el aviso *"no se encontraron enlaces de convocatorias"*. Para esos casos use una alerta de Google (abajo).

### Cubrir todas las entidades con alertas de Google
1. En <https://www.google.com/alerts> cree una alerta, por ejemplo:
   `("prestación de servicios profesionales" OR convocatoria OR "hoja de vida") (contratación OR contractual) site:gov.co`
2. En *Mostrar opciones → Enviar a*, elija **Feed RSS** y copie la URL del feed.
3. Péguela en `rss.feeds` y active la entrada. El sistema extrae el enlace real y aplica la lista blanca de dominios.

### Agregar otra fuente con API
Cree `scripts/rastreador/fuentes/mi_fuente.py` con `buscar(config, ctx)` y regístrela en `scripts/rastreador/fuentes/__init__.py`. Las instrucciones están al inicio de ese archivo.

## 3. Perfiles: buscar para cualquier persona o cargo

Cada archivo en `config/perfiles/` es un perfil. Todos los perfiles activos se evalúan en cada ejecución y el tablero permite cambiar entre ellos.

1. Copie `config/perfiles/_plantilla.json` como `config/perfiles/trabajo-social.json`.
2. Ponga `"id": "trabajo-social"` (igual al nombre del archivo) y llene roles, palabras clave, exclusiones y ubicación.
3. Valide y pruebe:
   ```bash
   python scripts/validar_perfil.py config/perfiles/trabajo-social.json \
     --titulo "Profesional social para acompañamiento comunitario" \
     --texto "Trabajo con víctimas y enfoque diferencial" --ubicacion "Bogotá"
   ```
4. Suba el archivo. En la siguiente ejecución, todas las ofertas encontradas se evalúan también contra ese perfil. Para publicar el resultado sin esperar vacantes nuevas, ejecute el flujo con *publicar_siempre*.

Para pausar un perfil sin borrarlo, use `"activo": false`.

**Crear un perfil a partir de una hoja de vida sin publicarla:** pídale a un asistente de IA, en su equipo, *"Genera un perfil con la estructura de `_plantilla.json` a partir de esta hoja de vida, sin nombre, contacto, entidades donde trabajó ni datos sensibles"*. Revise el resultado antes de subirlo.

### Cómo se calcula la afinidad
| Elemento | Puntos (por defecto) |
|---|---|
| Un cargo de `roles_objetivo` en el **título** | +8 (en el texto: +4) |
| Cada término de `palabras_clave_principales` | +3 |
| Cada término de `palabras_clave_secundarias` | +1 |
| Ciudad preferida | +2 |
| Cada término de `palabras_penalizacion` | −6 (resta, no descarta) |
| Un término de `palabras_exclusion` | descarta la oferta |
| Ubicación o modalidad no aceptadas | descarta la oferta |

`afinidad = puntos / puntaje_crudo_para_100 × 100` (máximo 100). Solo se guardan las ofertas que alcanzan `afinidad_minima_para_guardar` en al menos un perfil. La comparación ignora mayúsculas y tildes, y busca palabras o frases completas.

## 4. Tablero y CRM

- **Filtros:** perfil, afinidad mínima, fecha de publicación, texto (incluye sus notas), estado, fuente y orden. También puede ocultar las convocatorias ya cerradas.
- **Estados:** Por revisar, Postulada, Entrevista y Descartada. Puede agregar notas rápidas; se guardan solas.
- **Respaldo:** *Exportar progreso* descarga un JSON. *Importar progreso* lo fusiona y conserva el cambio más reciente de cada vacante. Úselo para pasar su seguimiento a otro navegador o equipo.
- Las vacantes que salen del listado (se archivan a los 60 días) pero tienen estado o notas se conservan en *Seguimiento de vacantes que ya no están en el listado*.

## 5. Privacidad

- Al repositorio solo suben **perfiles anónimos** y **ofertas públicas**. El `.gitignore` bloquea archivos `.pdf`, `.docx` y los respaldos del CRM para evitar subir una hoja de vida por error.
- Estados y notas viven en el `localStorage` de su navegador. No se envían a GitHub ni a ningún servidor.
- El tablero tiene `noindex` para que los buscadores no lo indexen. Aun así, quien tenga la dirección puede verlo.

## 6. Uso local y pruebas

```bash
python scripts/buscar_ofertas.py --simulacion        # consulta las fuentes y muestra resultados sin guardar
python scripts/buscar_ofertas.py --fuente paginas_oficiales
python -m unittest discover -s tests -v              # pruebas sin conexión
python -m http.server -d docs 8000                   # ver el tablero en http://localhost:8000
```

Use las consultas con moderación: el flujo hace una sola ronda diaria e identifica el rastreador en el encabezado `User-Agent`.
