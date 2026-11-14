/* Radar de vacantes – dashboard + CRM local.
 * Lee data/ofertas.json (generado por GitHub Actions) y guarda estados y notas
 * solo en el localStorage de este navegador. No envía datos a ningún servidor. */
(() => {
  "use strict";

  const CLAVE_CRM = "radar-vacantes:crm:v1";
  const CLAVE_FILTROS = "radar-vacantes:filtros:v1";
  const CLAVE_VISITA = "radar-vacantes:ultima-visita:v1";
  const ESTADOS = ["Por revisar", "Postulada", "Entrevista", "Descartada"];
  const ESTADO_INICIAL = "Por revisar";
  const NOMBRES_FUENTE = { reliefweb: "ReliefWeb (ONU)", paginas_oficiales: "Páginas oficiales", rss: "Feeds oficiales" };
  const TIPOS = { vacante: "Vacante", convocatoria: "Convocatoria", proceso: "Proceso" };

  const $ = (sel) => document.querySelector(sel);
  const hoy = new Date();

  /* ---------- almacenamiento seguro ---------- */
  const leer = (clave, defecto) => {
    try { const v = localStorage.getItem(clave); return v ? JSON.parse(v) : defecto; } catch { return defecto; }
  };
  const escribir = (clave, valor) => {
    try { localStorage.setItem(clave, JSON.stringify(valor)); return true; } catch { return false; }
  };

  let datos = { ofertas: [], perfiles: [], estado_fuentes: {} };
  let crm = leer(CLAVE_CRM, { version: 1, items: {} });
  if (!crm || typeof crm.items !== "object") crm = { version: 1, items: {} };
  const ultimaVisita = leer(CLAVE_VISITA, null);
  const filtros = Object.assign(
    { perfil: "", texto: "", afinidad: 0, periodo: "0", estado: "__activas", fuente: "", orden: "afinidad", abiertas: false },
    leer(CLAVE_FILTROS, {})
  );

  /* ---------- utilidades ---------- */
  const normalizar = (t) => (t || "").toString().normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const fecha = (iso) => (iso ? new Date(iso.length === 10 ? iso + "T12:00:00" : iso) : null);
  const fmtFecha = (iso, opciones = { day: "numeric", month: "short", year: "numeric" }) => {
    const d = fecha(iso);
    return d && !isNaN(d) ? d.toLocaleDateString("es-CO", opciones) : "";
  };
  const diasDesde = (iso) => { const d = fecha(iso); return d ? (hoy - d) / 86400000 : Infinity; };
  const estaCerrada = (o) => o.fecha_cierre && fecha(o.fecha_cierre) < new Date(hoy.toDateString());
  const estadoDe = (id) => (crm.items[id] && crm.items[id].estado) || ESTADO_INICIAL;
  const notaDe = (id) => (crm.items[id] && crm.items[id].nota) || "";
  const esNueva = (o) => ultimaVisita && o.fecha_detectada && o.fecha_detectada > ultimaVisita;

  const afinidadDe = (o) => {
    if (filtros.perfil && filtros.perfil !== "__todos") return o.afinidad[filtros.perfil] || null;
    const valores = Object.values(o.afinidad || {});
    return valores.length ? valores.reduce((a, b) => (b.puntaje > a.puntaje ? b : a)) : null;
  };

  let temporizadorAviso;
  const avisar = (texto) => {
    const el = $("#aviso");
    el.textContent = texto;
    el.classList.add("visible");
    clearTimeout(temporizadorAviso);
    temporizadorAviso = setTimeout(() => el.classList.remove("visible"), 3200);
  };

  /* ---------- CRM ---------- */
  const guardarCrm = () => {
    crm.actualizado = new Date().toISOString();
    if (!escribir(CLAVE_CRM, crm)) avisar("No se pudo guardar en este navegador (¿modo privado?). Exporta tu progreso.");
  };

  const actualizarItem = (oferta, cambios) => {
    const previo = crm.items[oferta.id] || { estado: ESTADO_INICIAL, nota: "" };
    const item = Object.assign({}, previo, cambios, {
      actualizado: new Date().toISOString(),
      ref: { titulo: oferta.titulo, organizacion: oferta.organizacion, url: oferta.url, fuente: oferta.fuente },
    });
    if (item.estado === ESTADO_INICIAL && !item.nota) delete crm.items[oferta.id];
    else crm.items[oferta.id] = item;
    guardarCrm();
  };

  /* ---------- filtros ---------- */
  const guardarFiltros = () => escribir(CLAVE_FILTROS, filtros);

  const pasaFiltros = (o) => {
    const af = afinidadDe(o);
    if (!af || af.puntaje < filtros.afinidad) return false;
    if (filtros.fuente && o.fuente !== filtros.fuente) return false;
    if (filtros.abiertas && estaCerrada(o)) return false;
    const periodo = Number(filtros.periodo);
    if (periodo && diasDesde(o.fecha_publicacion || o.fecha_detectada) > periodo) return false;
    const estado = estadoDe(o.id);
    if (filtros.estado === "__activas" && estado === "Descartada") return false;
    if (filtros.estado === "__nuevas" && !esNueva(o)) return false;
    if (!filtros.estado.startsWith("__") && estado !== filtros.estado) return false;
    if (filtros.texto) {
      const pajar = normalizar([o.titulo, o.organizacion, o.ubicacion, o.resumen, notaDe(o.id),
        (af.coincidencias || []).join(" ")].join(" "));
      if (!normalizar(filtros.texto).split(/\s+/).every((p) => pajar.includes(p))) return false;
    }
    return true;
  };

  const ordenar = (lista) => {
    const porFecha = (o) => o.fecha_publicacion || (o.fecha_detectada || "").slice(0, 10);
    const copia = lista.slice();
    if (filtros.orden === "reciente") copia.sort((a, b) => porFecha(b).localeCompare(porFecha(a)));
    else if (filtros.orden === "cierre") copia.sort((a, b) => (a.fecha_cierre || "9999").localeCompare(b.fecha_cierre || "9999"));
    else copia.sort((a, b) => afinidadDe(b).puntaje - afinidadDe(a).puntaje || porFecha(b).localeCompare(porFecha(a)));
    return copia;
  };

  /* ---------- render ---------- */
  const crearEtiqueta = (texto, clase = "") => {
    const s = document.createElement("span");
    s.className = `etiqueta ${clase}`.trim();
    s.textContent = texto;
    return s;
  };
  const crearChip = (texto, clase = "") => {
    const s = document.createElement("span");
    s.className = `chip ${clase}`.trim();
    s.textContent = texto;
    return s;
  };

  const tarjeta = (o) => {
    const nodo = $("#plantilla-oferta").content.firstElementChild.cloneNode(true);
    const af = afinidadDe(o);
    const estado = estadoDe(o.id);
    nodo.dataset.estado = estado;
    nodo.dataset.id = o.id;

    const anillo = nodo.querySelector(".oferta__afinidad");
    anillo.style.setProperty("--p", af.puntaje);
    anillo.classList.add(af.puntaje >= 70 ? "alta" : af.puntaje >= 50 ? "media" : "baja");
    anillo.querySelector("span").textContent = `${af.puntaje}%`;
    anillo.setAttribute("title", `Afinidad ${af.puntaje}%`);

    const etiquetas = nodo.querySelector(".oferta__etiquetas");
    etiquetas.append(crearEtiqueta(TIPOS[o.tipo] || "Vacante"));
    if (esNueva(o)) etiquetas.append(crearEtiqueta("Nueva", "etiqueta--nueva"));
    if (o.fecha_cierre) {
      etiquetas.append(estaCerrada(o)
        ? crearEtiqueta("Cerrada", "etiqueta--cerrada")
        : crearEtiqueta(`Cierra ${fmtFecha(o.fecha_cierre, { day: "numeric", month: "short" })}`, "etiqueta--cierre"));
    }

    const enlace = nodo.querySelector(".oferta__titulo a");
    enlace.href = o.url;
    enlace.textContent = o.titulo;

    nodo.querySelector(".oferta__org").textContent = [o.organizacion, o.ubicacion].filter(Boolean).join(" · ");
    const fuente = o.fuente_detalle || NOMBRES_FUENTE[o.fuente] || o.fuente;
    const meta = [fuente];
    if (o.fecha_publicacion) meta.push(`Publicada ${fmtFecha(o.fecha_publicacion)}`);
    if (o.fecha_detectada) meta.push(`Detectada ${fmtFecha(o.fecha_detectada)}`);
    nodo.querySelector(".oferta__meta").textContent = meta.join(" · ");

    const chips = nodo.querySelector(".oferta__chips");
    if (af.rol) chips.append(crearChip(af.rol, "chip--rol"));
    (af.coincidencias || []).slice(0, 8).forEach((c) => chips.append(crearChip(c)));
    if ((af.coincidencias || []).length > 8) chips.append(crearChip(`+${af.coincidencias.length - 8}`));
    (af.penalizaciones || []).forEach((p) => chips.append(crearChip(`Resta: ${p}`, "chip--resta")));

    const resumen = nodo.querySelector(".oferta__resumen");
    if (o.resumen) resumen.querySelector("p").textContent = o.resumen;
    else resumen.remove();

    const select = nodo.querySelector(".crm-estado");
    select.value = estado;
    select.setAttribute("aria-label", `Estado de ${o.titulo}`);
    select.addEventListener("change", () => {
      actualizarItem(o, { estado: select.value });
      nodo.dataset.estado = select.value;
      actualizarContadores();
      avisar(`Marcada como «${select.value}»`);
    });

    const nota = nodo.querySelector(".crm-nota");
    const marca = nodo.querySelector(".crm-guardado");
    nota.value = notaDe(o.id);
    nota.setAttribute("aria-label", `Notas de ${o.titulo}`);
    let t;
    nota.addEventListener("input", () => {
      marca.textContent = "…";
      clearTimeout(t);
      t = setTimeout(() => { actualizarItem(o, { nota: nota.value.trim() }); marca.textContent = "guardado"; }, 600);
    });
    return nodo;
  };

  const actualizarContadores = () => {
    const visibles = datos.ofertas.filter((o) => afinidadDe(o));
    const cuenta = { "Por revisar": 0, Postulada: 0, Entrevista: 0, Descartada: 0 };
    visibles.forEach((o) => { cuenta[estadoDe(o.id)] += 1; });
    $("#n-nuevas").textContent = visibles.filter(esNueva).length;
    $("#n-por-revisar").textContent = cuenta["Por revisar"];
    $("#n-postulada").textContent = cuenta.Postulada;
    $("#n-entrevista").textContent = cuenta.Entrevista;
    $("#n-descartada").textContent = cuenta.Descartada;
    document.querySelectorAll(".tarjeta-estado").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.estado === filtros.estado)));
  };

  const renderLista = () => {
    const lista = $("#lista");
    lista.replaceChildren();
    const resultado = ordenar(datos.ofertas.filter(pasaFiltros));
    const conPerfil = datos.ofertas.filter((o) => afinidadDe(o)).length;
    $("#conteo").textContent = `${resultado.length} de ${conPerfil} vacantes`;

    if (!resultado.length) {
      const v = document.createElement("div");
      v.className = "vacio";
      const s = document.createElement("strong");
      s.textContent = datos.ofertas.length ? "Ninguna vacante coincide con los filtros." : "Aún no hay vacantes registradas.";
      v.append(s, document.createTextNode(datos.ofertas.length
        ? "Prueba a bajar la afinidad mínima, ampliar el periodo o limpiar los filtros."
        : "Se llenará después de la primera ejecución diaria del flujo en GitHub Actions."));
      lista.append(v);
    } else {
      const frag = document.createDocumentFragment();
      resultado.forEach((o) => frag.append(tarjeta(o)));
      lista.append(frag);
    }
    actualizarContadores();
    renderArchivadas();
  };

  const renderArchivadas = () => {
    const actuales = new Set(datos.ofertas.map((o) => o.id));
    const archivadas = Object.entries(crm.items).filter(([id]) => !actuales.has(id));
    const panel = $("#panel-archivadas");
    panel.hidden = !archivadas.length;
    $("#n-archivadas").textContent = archivadas.length ? `(${archivadas.length})` : "";
    const ul = $("#archivadas");
    ul.replaceChildren();
    archivadas.sort((a, b) => (b[1].actualizado || "").localeCompare(a[1].actualizado || "")).forEach(([, item]) => {
      const li = document.createElement("li");
      const ref = item.ref || {};
      const a = document.createElement(ref.url ? "a" : "span");
      if (ref.url) { a.href = ref.url; a.target = "_blank"; a.rel = "noopener noreferrer"; }
      a.textContent = ref.titulo || "Vacante sin título";
      const b = document.createElement("strong");
      b.textContent = ` · ${item.estado}`;
      li.append(a, b);
      if (ref.organizacion) li.append(document.createTextNode(` · ${ref.organizacion}`));
      if (item.nota) {
        const p = document.createElement("div");
        p.className = "panel__nota";
        p.textContent = item.nota;
        li.append(p);
      }
      ul.append(li);
    });
  };

  const renderFuentes = () => {
    const ul = $("#fuentes");
    ul.replaceChildren();
    const entradas = Object.entries(datos.estado_fuentes || {});
    if (!entradas.length) {
      const li = document.createElement("li");
      li.textContent = "Sin información todavía.";
      ul.append(li);
      return;
    }
    entradas.forEach(([nombre, e]) => {
      const li = document.createElement("li");
      const estado = document.createElement("span");
      estado.className = e.ok ? "estado-ok" : e.omitida ? "estado-omitida" : "estado-error";
      estado.textContent = e.ok ? "Funcionando" : e.omitida ? "Omitida" : "Con error";
      li.append(document.createTextNode(`${NOMBRES_FUENTE[nombre] || nombre}: `), estado);
      li.append(document.createTextNode(e.ok
        ? ` · ${e.obtenidas} leídas, ${e.relevantes} relevantes, ${e.nuevas} nuevas en la última ejecución con cambios`
        : ` · ${e.mensaje || ""}`));
      (e.avisos || []).slice(0, 5).forEach((aviso) => {
        const d = document.createElement("div");
        d.className = "panel__nota";
        d.textContent = aviso;
        li.append(d);
      });
      ul.append(li);
    });
  };

  const renderSelects = () => {
    const sel = $("#perfil");
    sel.replaceChildren();
    const perfiles = datos.perfiles || [];
    if (perfiles.length > 1) sel.append(new Option("Todos los perfiles (mejor puntaje)", "__todos"));
    perfiles.forEach((p) => sel.append(new Option(p.nombre, p.id)));
    if (!perfiles.length) sel.append(new Option("Sin perfiles", ""));
    const ids = perfiles.map((p) => p.id).concat(perfiles.length > 1 ? ["__todos"] : []);
    if (!ids.includes(filtros.perfil)) filtros.perfil = perfiles[0] ? perfiles[0].id : "";
    sel.value = filtros.perfil;

    const fuentes = [...new Set(datos.ofertas.map((o) => o.fuente))];
    const fs = $("#f-fuente");
    fs.replaceChildren(new Option("Todas", ""));
    fuentes.forEach((f) => fs.append(new Option(NOMBRES_FUENTE[f] || f, f)));
    if (!fuentes.includes(filtros.fuente)) filtros.fuente = "";
  };

  const sincronizarControles = () => {
    $("#perfil").value = filtros.perfil;
    $("#f-texto").value = filtros.texto;
    $("#f-afinidad").value = filtros.afinidad;
    $("#f-afinidad-valor").textContent = `${filtros.afinidad}%`;
    $("#f-periodo").value = filtros.periodo;
    $("#f-estado").value = filtros.estado;
    $("#f-fuente").value = filtros.fuente;
    $("#f-orden").value = filtros.orden;
    $("#f-abiertas").checked = !!filtros.abiertas;
  };

  /* ---------- exportar / importar ---------- */
  const exportar = () => {
    const contenido = {
      app: "radar-vacantes", version: 1, exportado: new Date().toISOString(),
      total: Object.keys(crm.items).length, items: crm.items,
    };
    const blob = new Blob([JSON.stringify(contenido, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `radar-vacantes-progreso-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.append(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
    avisar(`Progreso exportado (${contenido.total} vacantes con seguimiento).`);
  };

  const importar = async (archivo) => {
    try {
      const contenido = JSON.parse(await archivo.text());
      if (!contenido || contenido.app !== "radar-vacantes" || typeof contenido.items !== "object") {
        throw new Error("El archivo no es un respaldo de este tablero.");
      }
      let nuevos = 0, actualizados = 0;
      Object.entries(contenido.items).forEach(([id, item]) => {
        if (!item || !ESTADOS.includes(item.estado)) return;
        const actual = crm.items[id];
        if (!actual) { crm.items[id] = item; nuevos += 1; }
        else if ((item.actualizado || "") > (actual.actualizado || "")) { crm.items[id] = item; actualizados += 1; }
      });
      guardarCrm();
      renderLista();
      avisar(`Importación lista: ${nuevos} nuevas y ${actualizados} actualizadas.`);
    } catch (e) {
      avisar(`No se pudo importar: ${e.message}`);
    }
  };

  /* ---------- eventos ---------- */
  const enlazar = () => {
    const cambio = (sel, clave, transformar = (v) => v, evento = "change") =>
      $(sel).addEventListener(evento, (ev) => {
        filtros[clave] = transformar(ev.target.type === "checkbox" ? ev.target.checked : ev.target.value);
        if (clave === "afinidad") $("#f-afinidad-valor").textContent = `${filtros.afinidad}%`;
        guardarFiltros();
        renderLista();
      });
    cambio("#perfil", "perfil");
    cambio("#f-texto", "texto", (v) => v, "input");
    cambio("#f-afinidad", "afinidad", Number, "input");
    cambio("#f-periodo", "periodo");
    cambio("#f-estado", "estado");
    cambio("#f-fuente", "fuente");
    cambio("#f-orden", "orden");
    cambio("#f-abiertas", "abiertas");

    document.querySelectorAll(".tarjeta-estado").forEach((b) => b.addEventListener("click", () => {
      filtros.estado = filtros.estado === b.dataset.estado ? "__activas" : b.dataset.estado;
      $("#f-estado").value = filtros.estado;
      guardarFiltros();
      renderLista();
    }));

    $("#limpiar").addEventListener("click", () => {
      Object.assign(filtros, { texto: "", afinidad: 0, periodo: "0", estado: "__activas", fuente: "", orden: "afinidad", abiertas: false });
      sincronizarControles();
      guardarFiltros();
      renderLista();
    });
    $("#exportar").addEventListener("click", exportar);
    $("#importar").addEventListener("change", (ev) => {
      if (ev.target.files[0]) importar(ev.target.files[0]);
      ev.target.value = "";
    });
  };

  /* ---------- inicio ---------- */
  const iniciar = async () => {
    enlazar();
    try {
      const resp = await fetch(`data/ofertas.json?v=${Date.now()}`, { cache: "no-store" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      datos = await resp.json();
      datos.ofertas = Array.isArray(datos.ofertas) ? datos.ofertas : [];
      $("#actualizado").textContent = datos.actualizado
        ? `Actualizado el ${fmtFecha(datos.actualizado, { day: "numeric", month: "long", year: "numeric", hour: "numeric", minute: "2-digit" })} · ${datos.ofertas.length} vacantes`
        : "Aún sin datos";
    } catch (e) {
      $("#actualizado").textContent = "No se pudieron cargar las vacantes";
      avisar(location.protocol === "file:"
        ? "Abre el tablero desde GitHub Pages o un servidor local (no como archivo)."
        : `Error al leer data/ofertas.json (${e.message}).`);
    }
    renderSelects();
    sincronizarControles();
    renderFuentes();
    renderLista();
    escribir(CLAVE_VISITA, new Date().toISOString());
  };

  document.addEventListener("DOMContentLoaded", iniciar);
})();
