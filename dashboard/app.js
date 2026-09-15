// Brassboard console: editor, controls, registers and trace. The emulator runs in worker.js.

const REGISTER_NAMES = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "X", "Y", "SP", "PC"];
const REGISTERS = new Set(REGISTER_NAMES);
const FLAGS = [["Z", 0x01], ["C", 0x02], ["V", 0x04], ["S", 0x08]];
const LINE_HEIGHT = 22;
const TRACE_KEEP = 200;
const DEFAULT_EXAMPLE = "fibonacci.asm";

const $ = (id) => document.getElementById(id);
const el = {
  program: $("program"), reset: $("k-reset"), step: $("k-step"), run: $("k-run"),
  lampRun: $("lamp-run"), lampBreak: $("lamp-break"), lampHalt: $("lamp-halt"),
  clock: $("clock"), clockOut: $("clockOut"), cycle: $("cycle"),
  source: $("source"), highlight: $("highlight"), gutter: $("gutter"), editorStatus: $("editorStatus"),
  editorMeta: $("editorMeta"), regs: $("regs"), traceBody: $("traceBody"), traceScroll: $("traceScroll"),
  traceMeta: $("traceMeta"), python: $("python"),
};

// ---------- Per-viewer storage (best effort) ----------
const store = {
  get(key, fallback) {
    try {
      const value = localStorage.getItem("brassboard:" + key);
      return value === null ? fallback : JSON.parse(value);
    } catch (e) { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem("brassboard:" + key, JSON.stringify(value)); } catch (e) { /* storage unavailable */ }
  },
};

// ---------- App state ----------
let ready = false;
let fatal = null;
let running = false;
let state = null;
let trace = [];
let lineAddresses = new Map();
let breakpoints = new Set(store.get("breakpoints", []));
let loadTimer = null;
let lastCurrentLine = null;

const worker = new Worker("worker.js");
const send = (type, args = {}) => worker.postMessage({ type, args });

worker.onmessage = ({ data }) => {
  if (data.type === "ready") {
    ready = true;
    el.python.textContent = `Python ${data.python} · in your browser`;
    fillExamples(data.examples);
    loadNow();
  } else if (data.type === "fatal") {
    fatal = data.message;
    renderStatus();
  } else if (data.type === "result") {
    applyResult(data);
  }
};

function applyResult(result) {
  if (result.clear_trace) trace = [];
  if (result.trace.length) {
    trace.push(...result.trace);
    if (trace.length > TRACE_KEEP) trace = trace.slice(-TRACE_KEEP);
  }
  running = result.running;
  state = result.state;
  const newLines = state.program ? new Map(state.program.lines) : new Map();
  const addressesChanged = newLines.size !== lineAddresses.size ||
    [...newLines].some(([line, address]) => lineAddresses.get(line) !== address);
  lineAddresses = newLines;
  breakpoints = new Set(state.breakpoints);
  store.set("breakpoints", [...breakpoints]);
  if (addressesChanged) renderSource();
  render();
}

// ---------- Loading programs ----------
function fillExamples(names) {
  const current = store.get("example", DEFAULT_EXAMPLE);
  el.program.innerHTML = names.map((n) => `<option value="${n}">${n}</option>`).join("") +
    `<option value="">My program</option>`;
  el.program.value = names.includes(current) ? current : "";
  el.program.disabled = false;
}

async function openExample(name) {
  const response = await fetch(`../examples/${name}`);
  if (!response.ok) return;
  el.source.value = await response.text();
  breakpoints = new Set();
  store.set("example", name);
  sourceChanged(true);
}

function loadNow() {
  clearTimeout(loadTimer);
  loadTimer = null;
  if (ready) send("load", { source: el.source.value, breakpoints: [...breakpoints] });
}

function sourceChanged(immediately) {
  store.set("source", el.source.value);
  renderSource();
  clearTimeout(loadTimer);
  if (immediately) loadNow();
  else loadTimer = setTimeout(loadNow, 400);
}

// ---------- Editor ----------
const escapeHtml = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function highlightLine(line) {
  const semicolon = line.indexOf(";");
  let code = semicolon >= 0 ? line.slice(0, semicolon) : line;
  const comment = semicolon >= 0 ? line.slice(semicolon) : "";
  let out = "";
  const label = code.match(/^(\s*)([^,:\s][^,:]*?)(\s*:)/);
  if (label) {
    out += escapeHtml(label[1]) + `<span class="lb">${escapeHtml(label[2])}</span>` + escapeHtml(label[3]);
    code = code.slice(label[0].length);
  }
  let index = 0;
  for (const piece of code.split(/(,)/)) {
    if (piece === ",") { out += ","; continue; }
    const [, before, token, after] = piece.match(/^(\s*)(.*?)(\s*)$/);
    let html = "";
    if (token) {
      let cls = "lb";
      if (index === 0) cls = "mn";
      else if (REGISTERS.has(token.toUpperCase())) cls = "rg";
      else if (/^(0x[0-9a-f]+|0b[01]+|0o[0-7]+|\d+)$/i.test(token)) cls = "nm";
      html = `<span class="${cls}">${escapeHtml(token)}</span>`;
      index++;
    }
    out += escapeHtml(before) + html + escapeHtml(after);
  }
  if (comment) out += `<span class="cm">${escapeHtml(comment)}</span>`;
  return out;
}

function renderSource() {
  const lines = el.source.value.split("\n");
  el.highlight.innerHTML = lines.map((line, i) => `<div class="hl-line" data-line="${i + 1}">${highlightLine(line) || " "}</div>`).join("");
  el.gutter.innerHTML = lines.map((_, i) => {
    const n = i + 1;
    const address = lineAddresses.get(n);
    const hasCode = address !== undefined;
    const addressText = hasCode ? address.toString(16).toUpperCase().padStart(4, "0") : "";
    return `<div class="g-row${hasCode ? " code" : ""}" data-line="${n}" title="${hasCode ? "Toggle breakpoint (F9)" : ""}">` +
      `<span class="bp"></span><span class="no">${n}</span><span class="ad">${addressText}</span></div>`;
  }).join("");
  syncScroll();
  renderMarks();
}

function renderMarks() {
  const current = state && !running ? state.current_line : null;
  const errorLine = state && state.status === "error" && state.error ? state.error.line : null;
  for (const row of el.gutter.children) {
    const n = Number(row.dataset.line);
    row.classList.toggle("bp-on", breakpoints.has(n));
    row.classList.toggle("cur", n === current);
    row.classList.toggle("err", n === errorLine);
  }
  for (const line of el.highlight.children) {
    const n = Number(line.dataset.line);
    line.classList.toggle("cur", n === current);
    line.classList.toggle("err", n === errorLine);
  }
  const focusLine = errorLine || current;
  if (focusLine && focusLine !== lastCurrentLine) scrollLineIntoView(focusLine);
  lastCurrentLine = focusLine;
}

function scrollLineIntoView(line) {
  const top = (line - 1) * LINE_HEIGHT;
  const view = el.source;
  if (top < view.scrollTop || top + LINE_HEIGHT * 2 > view.scrollTop + view.clientHeight) {
    view.scrollTop = Math.max(0, top - view.clientHeight / 3);
  }
}

function syncScroll() {
  el.highlight.style.transform = `translate(${-el.source.scrollLeft}px, ${-el.source.scrollTop}px)`;
  el.gutter.style.transform = `translateY(${-el.source.scrollTop}px)`;
}

function toggleBreakpoint(line) {
  const lineText = el.source.value.split("\n")[line - 1] || "";
  const allowed = state && state.program ? lineAddresses.has(line) : lineText.replace(/;.*/, "").trim() !== "";
  if (!allowed) return;
  if (breakpoints.has(line)) breakpoints.delete(line); else breakpoints.add(line);
  store.set("breakpoints", [...breakpoints]);
  renderMarks();
  if (ready) send("set_breakpoints", { lines: [...breakpoints] });
}

function caretLine() {
  return el.source.value.slice(0, el.source.selectionStart).split("\n").length;
}

// ---------- Rendering ----------
const hex = (value, width) => value.toString(16).toUpperCase().padStart(width, "0");

function render() {
  renderTransport();
  renderRegisters();
  renderTrace();
  renderMarks();
  renderStatus();
}

function renderTransport() {
  const status = state ? state.status : "empty";
  const canRun = ready && !["empty", "halted", "error"].includes(status);
  el.step.disabled = !canRun || running;
  el.run.disabled = !canRun && !running;
  el.run.textContent = running ? "Pause" : "Run";
  el.run.classList.toggle("primary", running);
  el.step.classList.toggle("primary", !running);
  el.reset.disabled = !ready || !(state && state.program);
  el.lampRun.classList.toggle("on", running);
  el.lampBreak.classList.toggle("on", !running && (status === "break" || status === "paused"));
  el.lampHalt.classList.toggle("on", status === "halted" || (status === "error" && !!(state && state.program)));
  const cycles = state ? state.cycles : 0;
  const digits = String(cycles);
  el.cycle.innerHTML = `<s>${"0".repeat(Math.max(0, 6 - digits.length))}</s>${digits}`;
}

function renderRegisters() {
  const registers = state ? state.registers : Array(16).fill(0);
  const written = new Set(state && !running ? state.written : []);
  const cards = REGISTER_NAMES.map((name, i) => {
    if (name === "F") return null;
    const value = registers[i];
    const wide = name === "PC" || name === "SP";
    const bits = wide ? "" : `<div class="bits" aria-hidden="true">${Array.from({ length: 8 }, (_, b) =>
      `<i class="${(value >> (7 - b)) & 1 ? "on" : ""}"></i>`).join("")}</div>`;
    return `<div class="reg${written.has(name) ? " changed" : ""}${value === 0 ? " zero" : ""}">` +
      `<div class="top"><span class="name">${name}</span><span class="dec">${value}</span></div>` +
      `<span class="hex">${hex(value, wide ? 4 : 2)}</span>${bits}</div>`;
  }).filter(Boolean);
  const flags = registers[5];
  cards.push(`<div class="reg${written.has("F") ? " changed" : ""}${flags === 0 ? " zero" : ""}">` +
    `<div class="top"><span class="name">F</span><span class="dec">${flags}</span></div>` +
    `<span class="hex">${hex(flags, 2)}</span>` +
    `<div class="flags">${FLAGS.map(([f, bit]) => `<span class="flag${flags & bit ? " on" : ""}"><i></i><b>${f}</b></span>`).join("")}</div></div>`);
  el.regs.innerHTML = cards.join("");
}

function effectHtml(effect) {
  return effect.split(" · ").map((part) => {
    let cls = "w";
    if (part.startsWith("PC ←") || part.startsWith("taken")) cls = "j";
    else if (part === "not taken") cls = "dim";
    else if (part === "halted") cls = "h";
    return `<span class="${cls}">${escapeHtml(part)}</span>`;
  }).join(" · ");
}

function renderTrace() {
  const rows = trace.map((e) => `<tr><td class="c">${e.cycle}</td><td class="a">${hex(e.address, 4)}</td>` +
    `<td class="b">${e.bytes.map((b) => hex(b, 2)).join(" ")}</td><td class="i">${escapeHtml(e.text)}</td>` +
    `<td class="fx">${effectHtml(e.effect)}</td></tr>`);
  if (state && state.next && !running) {
    const n = state.next;
    const atBreakpoint = state.status === "break" ? "breakpoint" : "";
    rows.push(`<tr class="next"><td class="c">next</td><td class="a">${hex(n.address, 4)}</td>` +
      `<td class="b">${n.bytes.map((b) => hex(b, 2)).join(" ")}</td><td class="i">${escapeHtml(n.text)}</td><td class="fx">${atBreakpoint}</td></tr>`);
  }
  el.traceBody.innerHTML = rows.join("");
  el.traceMeta.textContent = state ? `${state.cycles} cycles` : "";
  el.traceScroll.scrollTop = el.traceScroll.scrollHeight;
}

function renderStatus() {
  const box = el.editorStatus;
  box.classList.remove("bad", "good");
  if (fatal) {
    box.classList.add("bad");
    box.textContent = `Python could not be loaded: ${fatal}`;
    el.python.textContent = "Python unavailable";
    return;
  }
  if (!ready) {
    box.textContent = "Loading Python in your browser…";
    return;
  }
  if (!state) return;
  if (state.status === "error" && state.error) {
    box.classList.add("bad");
    const { line, message } = state.error;
    box.textContent = line ? `Line ${line}: ${message}` : message;
  } else if (state.program) {
    box.classList.add("good");
    const p = state.program;
    const bps = state.breakpoints.length;
    box.innerHTML = `<span>Assembled <b>✓</b></span><span>${p.labels} ${p.labels === 1 ? "label" : "labels"} · ${bps} ${bps === 1 ? "breakpoint" : "breakpoints"}</span>`;
  }
  el.editorMeta.textContent = state.program ? `${state.program.size} B` : "";
}

// ---------- Clock ----------
function clockSetting() {
  const v = Number(el.clock.value);
  if (v >= 100) return { rate: 0, max: true, label: "max" };
  const hz = Math.round(Math.pow(10, v / 25));
  const label = hz >= 1000 ? `${(hz / 1000).toFixed(hz >= 10000 ? 0 : 1)} kHz` : `${hz} Hz`;
  return { rate: hz, max: false, label };
}

function clockChanged() {
  const setting = clockSetting();
  el.clockOut.textContent = setting.label;
  store.set("clock", el.clock.value);
  if (running) send("rate", setting);
}

// ---------- Controls ----------
function doStep() { if (!el.step.disabled) send("step"); }
function doRunPause() {
  if (el.run.disabled) return;
  if (running) send("pause");
  else send("run", clockSetting());
}
function doReset() { if (!el.reset.disabled) send("reset"); }

el.step.addEventListener("click", doStep);
el.run.addEventListener("click", doRunPause);
el.reset.addEventListener("click", doReset);
el.clock.addEventListener("input", clockChanged);
el.program.addEventListener("change", () => {
  if (el.program.value) openExample(el.program.value);
  else store.set("example", "");
});

el.source.addEventListener("input", () => {
  if (el.program.value) { el.program.value = ""; store.set("example", ""); }
  sourceChanged(false);
});
el.source.addEventListener("scroll", syncScroll);
el.gutter.addEventListener("click", (event) => {
  const row = event.target.closest(".g-row");
  if (row) toggleBreakpoint(Number(row.dataset.line));
});
el.source.addEventListener("keydown", (event) => {
  if (event.key === "Tab") {
    event.preventDefault();
    const { selectionStart: start, selectionEnd: end, value } = el.source;
    el.source.value = value.slice(0, start) + "        " + value.slice(end);
    el.source.selectionStart = el.source.selectionEnd = start + 8;
    sourceChanged(false);
  }
});

document.addEventListener("keydown", (event) => {
  const onConsole = !$("p-console").hidden;
  if (!onConsole) return;
  if (event.key === "F10") { event.preventDefault(); if (event.shiftKey) return; doStep(); }
  else if (event.key === "F5") { event.preventDefault(); if (event.shiftKey) doReset(); else doRunPause(); }
  else if (event.key === "F9") { event.preventDefault(); toggleBreakpoint(caretLine()); }
  else if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) { event.preventDefault(); loadNow(); }
});

// ---------- Page tabs ----------
const pageTabs = ["console", "manual"];
function showPage(name, focus) {
  if (!pageTabs.includes(name)) name = "console";
  for (const t of pageTabs) {
    const on = t === name;
    $("t-" + t).setAttribute("aria-selected", String(on));
    $("t-" + t).tabIndex = on ? 0 : -1;
    $("p-" + t).hidden = !on;
  }
  if (focus) $("t-" + name).focus();
  store.set("tab", name);
}
pageTabs.forEach((t, i) => {
  $("t-" + t).addEventListener("click", () => { showPage(t); history.replaceState(null, "", "#" + t); });
  $("t-" + t).addEventListener("keydown", (e) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    showPage(pageTabs[(i + (e.key === "ArrowRight" ? 1 : pageTabs.length - 1)) % pageTabs.length], true);
  });
});

// ---------- Start ----------
async function start() {
  const hash = location.hash.slice(1);
  showPage(pageTabs.includes(hash) ? hash : store.get("tab", "console"));
  el.clock.value = store.get("clock", 27);
  clockChanged();

  const saved = store.get("source", null);
  const example = store.get("example", DEFAULT_EXAMPLE);
  if (saved !== null && !example) {
    el.source.value = saved;
  } else {
    try {
      const response = await fetch(`../examples/${example || DEFAULT_EXAMPLE}`);
      el.source.value = response.ok ? await response.text() : (saved || "");
    } catch (e) {
      el.source.value = saved || "";
    }
  }
  renderSource();
  render();
  if (ready) loadNow();
}
start();
