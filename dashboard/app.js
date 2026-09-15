// Brassboard console: editor, controls, registers, memory and trace. The emulator runs in worker.js.

const REGISTER_NAMES = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "X", "Y", "SP", "PC"];
const REGISTERS = new Set(REGISTER_NAMES);
const SP = 14;
const PC = 15;
const FLAGS = [["Z", 0x01], ["C", 0x02], ["V", 0x04], ["S", 0x08]];
const LINE_HEIGHT = 22;
const TRACE_KEEP = 200;
const DUMP_ROWS = 8;
const STACK_ROWS = 8;
const DEFAULT_EXAMPLE = "fibonacci.asm";

const $ = (id) => document.getElementById(id);
const el = {
  program: $("program"), ramSize: $("ramSize"), reset: $("k-reset"), step: $("k-step"), run: $("k-run"),
  lampRun: $("lamp-run"), lampBreak: $("lamp-break"), lampHalt: $("lamp-halt"),
  clock: $("clock"), clockOut: $("clockOut"), cycle: $("cycle"),
  source: $("source"), highlight: $("highlight"), gutter: $("gutter"), editorStatus: $("editorStatus"),
  editorMeta: $("editorMeta"), regs: $("regs"), traceBody: $("traceBody"), traceScroll: $("traceScroll"),
  traceMeta: $("traceMeta"), python: $("python"),
  ramMap: $("ramMap"), memAddress: $("memAddress"), memFollow: $("memFollow"), ramDump: $("ramDump"),
  stackList: $("stackList"), romDump: $("romDump"), memMeta: $("memMeta"),
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
let ram = new Uint8Array(1024);
let rom = new Uint8Array(0);
let labelsByAddress = new Map();
let labelsByName = new Map();
let traces = { all: [], ram: [], jump: [] };
let traceView = store.get("traceView", "all");
let lineAddresses = new Map();
let breakpoints = new Set(store.get("breakpoints", []));
let loadTimer = null;
let lastFocusLine = null;
let followSp = true;
let viewAddress = 0;

const worker = new Worker("worker.js");
const send = (type, args = {}) => worker.postMessage({ type, args });

worker.onmessage = ({ data }) => {
  if (data.type === "ready") {
    ready = true;
    el.python.textContent = `Python ${data.python} · in your browser`;
    fillExamples(data.examples);
    el.ramSize.disabled = false;
    loadNow();
  } else if (data.type === "fatal") {
    fatal = data.message;
    renderStatus();
  } else if (data.type === "result") {
    applyResult(data);
  }
};

const decodeBase64 = (text) => Uint8Array.from(atob(text), (c) => c.charCodeAt(0));

function applyResult(result) {
  if (result.clear_trace) traces = { all: [], ram: [], jump: [] };
  for (const entry of result.trace) {
    for (const view of ["all", "ram", "jump"]) {
      if (entry[view]) traces[view].push(entry);
    }
  }
  for (const view of ["all", "ram", "jump"]) {
    if (traces[view].length > TRACE_KEEP) traces[view] = traces[view].slice(-TRACE_KEEP);
  }

  running = result.running;
  state = result.state;
  ram = decodeBase64(state.memory.ram);
  if (state.program) {
    rom = decodeBase64(state.program.bytecode);
    labelsByAddress = new Map();
    for (const [name, address] of state.program.label_list) {
      if (!labelsByAddress.has(address)) labelsByAddress.set(address, name);
    }
    labelsByName = new Map(state.program.label_list);
  }

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
  if (ready) send("load", { source: el.source.value, breakpoints: [...breakpoints], ram_size: Number(el.ramSize.value) });
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
    const addressText = hasCode ? hex(address, 4) : "";
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
  if (focusLine && focusLine !== lastFocusLine) scrollLineIntoView(focusLine);
  lastFocusLine = focusLine;
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
  renderRom();
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
  renderMemory();
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
  const digits = String(state ? state.cycles : 0);
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

// ---------- Memory ----------
function memoryMarks() {
  const size = state ? state.memory.size : ram.length;
  const sp = state ? state.registers[SP] : size - 1;
  return {
    size, sp,
    returns: new Set(state ? state.memory.return_cells : []),
    writes: new Set(state && !running ? state.memory.last_writes : []),
  };
}

function cellKind(address, marks) {
  if (marks.writes.has(address)) return "wr";
  if (marks.returns.has(address)) return "ra";
  if (address >= marks.sp && address < marks.size - 1) return "sv";
  return ram[address] ? "nz" : "";
}

let mapColors = null;
function readMapColors() {
  const css = getComputedStyle(document.documentElement);
  const rgb = (name) => {
    const value = css.getPropertyValue(name).trim().replace("#", "");
    return [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16));
  };
  mapColors = { "": rgb("--lamp-off"), nz: rgb("--ink-3"), sv: rgb("--verdigris"), ra: rgb("--brass"), wr: rgb("--ink") };
}
window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => { readMapColors(); renderMemory(); });

function mapGeometry(size) {
  const cols = size > 4096 ? 256 : 64;
  const cell = size > 4096 ? 1 : 5;
  const gap = size > 4096 ? 0 : 1;
  return { cols, rows: Math.ceil(size / cols), cell, gap, pitch: cell + gap };
}

function drawMap(marks) {
  if (!mapColors) readMapColors();
  const g = mapGeometry(marks.size);
  const width = g.cols * g.pitch - g.gap;
  const height = g.rows * g.pitch - g.gap;
  const canvas = el.ramMap;
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const ctx = canvas.getContext("2d");
  const image = ctx.createImageData(width, height);
  const data = image.data;
  for (let address = 0; address < marks.size; address++) {
    const [r, gr, b] = mapColors[cellKind(address, marks)];
    const x0 = (address % g.cols) * g.pitch;
    const y0 = Math.floor(address / g.cols) * g.pitch;
    for (let y = y0; y < y0 + g.cell; y++) {
      for (let x = x0; x < x0 + g.cell; x++) {
        const i = (y * width + x) * 4;
        data[i] = r; data[i + 1] = gr; data[i + 2] = b; data[i + 3] = 255;
      }
    }
  }
  ctx.putImageData(image, 0, 0);
}

function dumpRows(bytes, firstRow, rowCount, classify) {
  const head = `<div class="hexrow hexhead"><span></span>${Array.from({ length: 16 }, (_, i) => `<span>${i.toString(16).toUpperCase()}</span>`).join("")}</div>`;
  let html = head;
  for (let row = 0; row < rowCount; row++) {
    const base = firstRow + row * 16;
    if (base >= bytes.length) break;
    let cells = "";
    for (let i = 0; i < 16; i++) {
      const address = base + i;
      if (address >= bytes.length) { cells += "<span></span>"; continue; }
      const classes = classify(address);
      cells += `<span class="${classes}" data-address="${address}">${hex(bytes[address], 2)}</span>`;
    }
    html += `<div class="hexrow"><span class="a">${hex(base, 4)}</span>${cells}</div>`;
  }
  return html;
}

function renderMemory() {
  const marks = memoryMarks();
  el.memMeta.textContent = `SP ${hex(marks.sp, 4)}`;
  drawMap(marks);

  const target = followSp ? marks.sp : Math.min(viewAddress, marks.size - 1);
  const lastRowStart = Math.max(0, Math.ceil(marks.size / 16) * 16 - DUMP_ROWS * 16);
  const firstRow = Math.min(Math.max(0, Math.floor(target / 16) * 16 - 32), lastRowStart);
  el.ramDump.innerHTML = dumpRows(ram, firstRow, DUMP_ROWS, (address) => {
    const kind = cellKind(address, marks);
    return [kind, address === marks.sp ? "sp" : "", !followSp && address === viewAddress ? "tgt" : ""].filter(Boolean).join(" ");
  });
  el.memFollow.setAttribute("aria-pressed", String(followSp));

  const rows = [];
  let address = marks.sp;
  while (address < marks.size - 1 && rows.length < STACK_ROWS) {
    if (marks.returns.has(address) && marks.returns.has(address + 1)) {
      const value = ram[address] | (ram[address + 1] << 8);
      const label = labelsByAddress.has(value) ? ` (${labelsByAddress.get(value)})` : "";
      rows.push(`<div class="srow ret"><span class="where">${address === marks.sp ? "SP →" : ""}</span><span>${hex(address, 4)}</span>` +
        `<span>${hex(ram[address], 2)} ${hex(ram[address + 1], 2)}</span><span class="d">ret ${hex(value, 4)}${escapeHtml(label)}</span></div>`);
      address += 2;
    } else {
      rows.push(`<div class="srow val"><span class="where">${address === marks.sp ? "SP →" : ""}</span><span>${hex(address, 4)}</span>` +
        `<span>${hex(ram[address], 2)}</span><span class="d">${ram[address]}</span></div>`);
      address += 1;
    }
  }
  const remaining = marks.size - 1 - address;
  if (remaining > 0) rows.push(`<div class="srow more"><span></span><span>…</span><span></span><span class="d">${remaining} more ${remaining === 1 ? "byte" : "bytes"}</span></div>`);
  if (!rows.length) rows.push(`<div class="srow more"><span class="where">SP →</span><span>${hex(marks.sp, 4)}</span><span></span><span class="d">empty</span></div>`);
  el.stackList.innerHTML = rows.join("");

  renderRom();
}

function renderRom() {
  const pc = state && state.next ? state.registers[PC] : -1;
  const breakAddresses = new Set([...breakpoints].map((line) => lineAddresses.get(line)).filter((a) => a !== undefined));
  el.romDump.innerHTML = rom.length
    ? dumpRows(rom, 0, Math.ceil(rom.length / 16), (address) =>
        [address === pc ? "pc" : "", breakAddresses.has(address) ? "bpa" : ""].filter(Boolean).join(" "))
    : "";
}

function resolveAddress(text) {
  const value = text.trim();
  if (!value) return null;
  if (labelsByName.has(value)) return labelsByName.get(value);
  if (/^(0x[0-9a-f]+|0b[01]+|0o[0-7]+|\d+)$/i.test(value)) {
    const number = value.startsWith("0b") || value.startsWith("0B") ? parseInt(value.slice(2), 2)
      : value.startsWith("0o") || value.startsWith("0O") ? parseInt(value.slice(2), 8)
      : Number(value);
    return Number.isInteger(number) ? number : undefined;
  }
  if (/^[0-9a-f]{1,4}$/i.test(value)) return parseInt(value, 16);
  return undefined;
}

function goToAddress() {
  const address = resolveAddress(el.memAddress.value);
  const size = state ? state.memory.size : ram.length;
  if (address === null) {
    followSp = true;
    el.memAddress.removeAttribute("aria-invalid");
  } else if (address === undefined || address >= size) {
    el.memAddress.setAttribute("aria-invalid", "true");
    return;
  } else {
    followSp = false;
    viewAddress = address;
    el.memAddress.removeAttribute("aria-invalid");
  }
  renderMemory();
}

// ---------- Trace ----------
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
  const entries = traces[traceView];
  const rows = entries.map((e) => `<tr><td class="c">${e.cycle}</td><td class="a">${hex(e.address, 4)}</td>` +
    `<td class="b">${e.bytes.map((b) => hex(b, 2)).join(" ")}</td><td class="i">${escapeHtml(e.text)}</td>` +
    `<td class="fx">${effectHtml(e.effect)}</td></tr>`);
  if (traceView === "all" && state && state.next && !running) {
    const n = state.next;
    rows.push(`<tr class="next"><td class="c">next</td><td class="a">${hex(n.address, 4)}</td>` +
      `<td class="b">${n.bytes.map((b) => hex(b, 2)).join(" ")}</td><td class="i">${escapeHtml(n.text)}</td>` +
      `<td class="fx">${state.status === "break" ? "breakpoint" : ""}</td></tr>`);
  }
  el.traceBody.innerHTML = rows.join("");
  for (const button of document.querySelectorAll("[data-trace]")) {
    button.setAttribute("aria-pressed", String(button.dataset.trace === traceView));
  }
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
el.ramSize.addEventListener("change", () => {
  store.set("ramSize", el.ramSize.value);
  followSp = true;
  el.memAddress.value = "";
  loadNow();
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

el.memAddress.addEventListener("keydown", (event) => { if (event.key === "Enter") goToAddress(); });
el.memAddress.addEventListener("change", goToAddress);
el.memFollow.addEventListener("click", () => {
  followSp = true;
  el.memAddress.value = "";
  el.memAddress.removeAttribute("aria-invalid");
  renderMemory();
});
el.ramMap.addEventListener("click", (event) => {
  const marks = memoryMarks();
  const g = mapGeometry(marks.size);
  const rect = el.ramMap.getBoundingClientRect();
  const x = Math.floor(((event.clientX - rect.left) / rect.width) * el.ramMap.width / g.pitch);
  const y = Math.floor(((event.clientY - rect.top) / rect.height) * el.ramMap.height / g.pitch);
  const address = y * g.cols + x;
  if (address < 0 || address >= marks.size) return;
  followSp = false;
  viewAddress = address;
  el.memAddress.value = hex(address, 4);
  renderMemory();
});
el.ramDump.addEventListener("click", (event) => {
  const cell = event.target.closest("[data-address]");
  if (!cell) return;
  followSp = false;
  viewAddress = Number(cell.dataset.address);
  el.memAddress.value = hex(viewAddress, 4);
  renderMemory();
});

const memTabs = [["tab-ram", "pane-ram"], ["tab-rom", "pane-rom"]];
for (const [tab] of memTabs) {
  $(tab).addEventListener("click", () => {
    for (const [t, pane] of memTabs) {
      $(t).setAttribute("aria-selected", String(t === tab));
      $(pane).hidden = t !== tab;
    }
  });
}

for (const button of document.querySelectorAll("[data-trace]")) {
  button.addEventListener("click", () => {
    traceView = button.dataset.trace;
    store.set("traceView", traceView);
    renderTrace();
  });
}

document.addEventListener("keydown", (event) => {
  if ($("p-console").hidden || event.target === el.memAddress) return;
  if (event.key === "F10") { event.preventDefault(); if (!event.shiftKey) doStep(); }
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
  el.ramSize.value = String(store.get("ramSize", "1024"));
  if (!el.ramSize.value) el.ramSize.value = "1024";
  ram = new Uint8Array(Number(el.ramSize.value));
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
