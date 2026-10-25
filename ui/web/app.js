const state = {
  tablas: [null, null], // { tipo, num_filas } por índice de captura (0/1), o null si no detectada
  modo: "ultima",
  filaElegida: null,
  ocupado: false,
};

const captureBtns = document.querySelectorAll("[data-capture]");

function setBusy(ocupado) {
  state.ocupado = ocupado;
  captureBtns.forEach((btn) => { btn.disabled = ocupado; });
  if (ocupado) {
    procesarBtn.disabled = true;
    exportarBtn.disabled = true;
    exportarXlsmBtn.disabled = true;
  } else {
    actualizarSeleccionFila();
    exportarBtn.disabled = resultCard.hidden;
    exportarXlsmBtn.disabled = resultCard.hidden;
  }
}

const statusEl = document.getElementById("status");
const procesarBtn = document.getElementById("btn-procesar");
const exportarBtn = document.getElementById("btn-exportar");
const exportarXlsmBtn = document.getElementById("btn-exportar-xlsm");
const resultCard = document.getElementById("result-card");
const modoUltima = document.getElementById("modo-ultima");
const modoElegir = document.getElementById("modo-elegir");
const selectFila = document.getElementById("select-fila");
const mismatchWarning = document.getElementById("mismatch-warning");

function setStatus(message, isError = false) {
  statusEl.textContent = message || "";
  statusEl.classList.toggle("status--error", isError);
}

function setBadge(index, done, text) {
  const badge = document.querySelector(`[data-badge="${index}"]`);
  badge.textContent = text;
  badge.classList.toggle("badge--done", done);
  badge.classList.toggle("badge--pending", !done);
}

function setDetectMsg(indice, texto, variante) {
  const el = document.querySelector(`[data-detect="${indice}"]`);
  el.textContent = texto || "";
  el.classList.toggle("detect-msg--ok", variante === "ok");
  el.classList.toggle("detect-msg--error", variante === "error");
}

function invalidarResultado() {
  resultCard.hidden = true;
  exportarBtn.disabled = true;
  exportarXlsmBtn.disabled = true;
  window.pywebview.api.invalidar_resultado();
}

function actualizarSeleccionFila() {
  const [t1, t2] = state.tablas;
  const ambasListas = Boolean(t1 && t2);

  modoUltima.disabled = !ambasListas;
  modoElegir.disabled = !ambasListas;
  selectFila.disabled = !ambasListas || state.modo !== "elegir";

  if (!ambasListas) {
    mismatchWarning.hidden = true;
    setBadge("process", false, "Esperando capturas");
    procesarBtn.disabled = true;
    return;
  }

  if (t1.num_filas !== t2.num_filas) {
    mismatchWarning.hidden = false;
    mismatchWarning.textContent =
      `Las capturas tienen distinta cantidad de filas (${t1.num_filas} y ${t2.num_filas}). ` +
      "Repita una captura antes de transcribir.";
    setBadge("process", false, "Filas no coinciden");
    procesarBtn.disabled = true;
    return;
  }

  mismatchWarning.hidden = true;
  const numFilas = t1.num_filas;

  const opcionesActuales = Array.from(selectFila.options).map((o) => o.value).join(",");
  const opcionesNuevas = Array.from({ length: numFilas }, (_, i) => String(i + 1)).join(",");
  if (opcionesActuales !== opcionesNuevas) {
    selectFila.innerHTML = "";
    for (let i = 1; i <= numFilas; i += 1) {
      const opt = document.createElement("option");
      opt.value = String(i);
      opt.textContent = `Fila ${i}`;
      selectFila.appendChild(opt);
    }
    selectFila.value = String(numFilas);
    state.filaElegida = numFilas;
  }

  const listo = state.modo === "ultima" || (state.modo === "elegir" && state.filaElegida);
  setBadge("process", listo, listo ? "Listo para transcribir" : "Elija una fila");
  procesarBtn.disabled = !listo;
}

async function capturar(indice) {
  if (state.ocupado) return;
  setBusy(true);
  setStatus(`Ocultando la app y capturando imagen ${indice}...`);
  const respuesta = await window.pywebview.api.capturar(indice);

  if (!respuesta.ok) {
    setStatus(respuesta.error, true);
    setBusy(false);
    return;
  }

  const preview = document.querySelector(`[data-preview="${indice}"]`);
  preview.src = respuesta.preview;
  preview.hidden = false;

  state.tablas[indice - 1] = null;
  invalidarResultado();

  if (!respuesta.tabla.ok) {
    setBadge(indice, false, "Error de detección");
    setDetectMsg(indice, respuesta.tabla.error, "error");
    setStatus(`Imagen ${indice} capturada, pero no se detectó la tabla.`, true);
  } else {
    state.tablas[indice - 1] = { tipo: respuesta.tabla.tipo, num_filas: respuesta.tabla.num_filas };
    setBadge(indice, true, "Capturada");
    setDetectMsg(indice, `${respuesta.tabla.num_filas} fila(s) detectada(s).`, "ok");
    setStatus(`Imagen ${indice} capturada y tabla detectada.`);
  }

  setBusy(false);
}

function renderResultado(resultado) {
  const tabla = document.getElementById("result-table");
  tabla.innerHTML = "";
  for (const [campo, valor] of Object.entries(resultado.resultado)) {
    const fila = document.createElement("tr");
    const celdaCampo = document.createElement("td");
    celdaCampo.textContent = campo;
    const celdaValor = document.createElement("td");
    celdaValor.textContent = valor === null || valor === undefined ? "—" : valor;
    fila.append(celdaCampo, celdaValor);
    tabla.appendChild(fila);
  }

  const avisos = document.getElementById("warnings");
  avisos.innerHTML = "";
  for (const aviso of resultado.avisos || []) {
    const item = document.createElement("li");
    item.textContent = aviso;
    avisos.appendChild(item);
  }

  resultCard.hidden = false;
  exportarBtn.disabled = false;
  exportarXlsmBtn.disabled = false;
}

async function procesar() {
  if (state.ocupado || procesarBtn.disabled) return;
  setBusy(true);
  setStatus("Transcribiendo fila seleccionada...");

  const fila = state.modo === "ultima" ? "ultima" : state.filaElegida;
  const respuesta = await window.pywebview.api.procesar(fila);

  if (!respuesta.ok) {
    setStatus(respuesta.error, true);
    setBusy(false);
    return;
  }

  renderResultado(respuesta.resultado);
  const pendientes = respuesta.resultado.campos_pendientes || [];
  setStatus(
    pendientes.length
      ? `Fila ${respuesta.fila}: ${pendientes.length} campo(s) pendiente(s).`
      : `Fila ${respuesta.fila}: lectura completa.`
  );
  setBusy(false);
}

async function exportar() {
  if (state.ocupado || exportarBtn.disabled) return;
  setBusy(true);
  const respuesta = await window.pywebview.api.exportar_csv();
  setBusy(false);
  if (!respuesta.ok) {
    setStatus(respuesta.error, true);
    return;
  }
  setStatus(`Archivo guardado en ${respuesta.path}`);
}

async function exportarXlsm() {
  if (state.ocupado || exportarXlsmBtn.disabled) return;
  setBusy(true);
  const respuesta = await window.pywebview.api.exportar_xlsm();
  setBusy(false);
  if (!respuesta.ok) {
    setStatus(respuesta.error, true);
    return;
  }
  setStatus(`Archivo guardado en ${respuesta.path}`);
}

document.querySelectorAll("[data-capture]").forEach((btn) => {
  btn.addEventListener("click", () => capturar(Number(btn.dataset.capture)));
});

modoUltima.addEventListener("change", () => {
  if (!modoUltima.checked) return;
  state.modo = "ultima";
  invalidarResultado();
  actualizarSeleccionFila();
});

modoElegir.addEventListener("change", () => {
  if (!modoElegir.checked) return;
  state.modo = "elegir";
  if (!state.filaElegida && selectFila.options.length) {
    state.filaElegida = Number(selectFila.value);
  }
  invalidarResultado();
  actualizarSeleccionFila();
});

selectFila.addEventListener("change", () => {
  state.filaElegida = Number(selectFila.value);
  invalidarResultado();
  actualizarSeleccionFila();
});

procesarBtn.addEventListener("click", procesar);
exportarBtn.addEventListener("click", exportar);
exportarXlsmBtn.addEventListener("click", exportarXlsm);

actualizarSeleccionFila();
