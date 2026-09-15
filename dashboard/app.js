// Brassboard console: programs, editor, controls, registers, data path, trace and memory.
// The emulator runs in worker.js.

const REGISTER_NAMES = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "X", "Y", "SP", "PC"];
const REGISTERS = new Set(REGISTER_NAMES);
const F = 5;
const SP = 14;
const PC = 15;
const FLAGS = [["Z", 0x01], ["C", 0x02], ["V", 0x04], ["S", 0x08]];
const LINE_HEIGHT = 22;
const TRACE_KEEP = 200;
const DUMP_ROWS = 8;
const STACK_ROWS = 8;
const DEFAULT_EXAMPLE = "fibonacci.asm";
const NEW_PROGRAM = "; new program\n\n        hlt\n";

const $ = (id) => document.getElementById(id);
const el = {
  program: $("program"), ramSize: $("ramSize"), reset: $("k-reset"), back: $("k-back"), step: $("k-step"), run: $("k-run"),
  lampRun: $("lamp-run"), lampBreak: $("lamp-break"), lampHalt: $("lamp-halt"),
  clock: $("clock"), clockOut: $("clockOut"), cycle: $("cycle"),
  source: $("source"), highlight: $("highlight"), gutter: $("gutter"), editorStatus: $("editorStatus"),
  editorMeta: $("editorMeta"), regs: $("regs"), traceBody: $("traceBody"), traceScroll: $("traceScroll"),
  traceMeta: $("traceMeta"), traceFilters: $("traceFilters"), python: $("python"),
  ramMap: $("ramMap"), memAddress: $("memAddress"), memFollow: $("memFollow"), ramDump: $("ramDump"),
  stackList: $("stackList"), romDump: $("romDump"), memMeta: $("memMeta"),
  pathMeta: $("pathMeta"), datapath: $("datapath"),
  programName: $("programName"), progNew: $("prog-new"), progDuplicate: $("prog-duplicate"),
  progOpen: $("prog-open"), progDownload: $("prog-download"), progDelete: $("prog-delete"), progFile: $("prog-file"),
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
let commandError = null;
let commandErrorTimer = null;
let running = false;
let state = null;
let ram = new Uint8Array(1024);
let rom = new Uint8Array(0);
let labelsByAddress = new Map();
let labelsByName = new Map();
let traces = { all: [], ram: [], jump: [] };
let traceView = store.get("traceView", "all");
let lineAddresses = new Map();
let breakpoints = new Set();
let loadTimer = null;
let lastFocusLine = null;
let followSp = true;
let viewAddress = 0;
let editing = null; // {kind: "reg", name, text} or {kind: "ram", address, text}
let programs = [];  // the viewer's own programs: {id, name, source, breakpoints}
let exampleNames = [];
let current = { kind: "example", name: DEFAULT_EXAMPLE };
let exampleBreakpoints = store.get("exampleBreakpoints", {});

const worker = new Worker("worker.js");
const send = (type, args = {}) => worker.postMessage({ type, args });

worker.onmessage = ({ data }) => {
  if (data.type === "ready") {
    ready = true;
    el.python.textContent = `Python ${data.python} · in your browser`;
    exampleNames = data.examples;
    fillProgramList();
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

function showCommandError(message) {
  commandError = message;
  clearTimeout(commandErrorTimer);
  commandErrorTimer = setTimeout(() => { commandError = null; renderStatus(); }, 6000);
  renderStatus();
}

function applyResult(result) {
  running = result.running;
  if (result.error) {
    renderTransport();
    showCommandError(result.error);
    return;
  }
  if (result.clear_trace) traces = { all: [], ram: [], jump: [] };
  state = result.state;
  if (result.rewound) {
    for (const view of ["all", "ram", "jump"]) traces[view] = traces[view].filter((e) => e.cycle <= state.cycles);
  }
  for (const entry of result.trace) {
    for (const view of ["all", "ram", "jump"]) {
      if (entry[view]) traces[view].push(entry);
    }
  }
  for (const view of ["all", "ram", "jump"]) {
    if (traces[view].length > TRACE_KEEP) traces[view] = traces[view].slice(-TRACE_KEEP);
  }

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
  persistBreakpoints();
  if (addressesChanged) renderSource();
  render();
}

// ---------- Programs ----------
// Examples come from the repository and can't be changed: typing in one saves the change as a copy
// under My programs. The viewer's own programs are saved in this browser as they are edited.
const newId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
const currentProgram = () => (current.kind === "mine" ? programs.find((p) => p.id === current.id) || null : null);
const saveProgramsNow = () => store.set("programs", programs);
const displayName = () => (currentProgram() ? currentProgram().name : current.name);

function uniqueName(base) {
  const names = new Set(programs.map((p) => p.name));
  if (!names.has(base)) return base;
  for (let n = 2; ; n++) {
    if (!names.has(`${base} ${n}`)) return `${base} ${n}`;
  }
}

function createProgram(name, source, programBreakpoints = []) {
  const program = { id: newId(), name: uniqueName(name), source, breakpoints: programBreakpoints };
  programs.unshift(program);
  saveProgramsNow();
  return program;
}

function fillProgramList() {
  const mine = programs.map((p) => `<option value="mine:${p.id}">${escapeHtml(p.name)}</option>`).join("");
  const examples = exampleNames.map((n) => `<option value="example:${escapeHtml(n)}">${escapeHtml(n)}</option>`).join("");
  el.program.innerHTML = (mine ? `<optgroup label="My programs">${mine}</optgroup>` : "") +
    (examples ? `<optgroup label="Examples">${examples}</optgroup>` : "");
  el.program.value = current.kind === "mine" ? `mine:${current.id}` : `example:${current.name}`;
  el.program.disabled = !el.program.options.length;
  const program = currentProgram();
  if (document.activeElement !== el.programName) el.programName.value = displayName();
  el.programName.disabled = !program;
  el.progDelete.disabled = !program;
}

async function openProgram(ref) {
  editing = null;
  if (ref.kind === "mine") {
    const program = programs.find((p) => p.id === ref.id);
    if (!program) return openProgram({ kind: "example", name: DEFAULT_EXAMPLE });
    current = { kind: "mine", id: program.id };
    el.source.value = program.source;
    breakpoints = new Set(program.breakpoints || []);
  } else {
    let text;
    try {
      const response = await fetch(`../examples/${ref.name}`);
      if (!response.ok) throw new Error(String(response.status));
      text = await response.text();
    } catch (e) {
      showCommandError(`could not open the example ${ref.name}`);
      return;
    }
    current = { kind: "example", name: ref.name };
    el.source.value = text;
    breakpoints = new Set(exampleBreakpoints[ref.name] || []);
  }
  store.set("current", current);
  lineAddresses = new Map();
  lastFocusLine = null;
  el.source.scrollTop = 0;
  if (document.activeElement === el.programName) el.programName.blur();
  fillProgramList();
  el.programName.value = displayName();
  renderSource();
  loadNow();
}

function persistBreakpoints() {
  const program = currentProgram();
  if (program) {
    program.breakpoints = [...breakpoints];
    saveProgramsNow();
  } else if (current.kind === "example") {
    exampleBreakpoints[current.name] = [...breakpoints];
    store.set("exampleBreakpoints", exampleBreakpoints);
  }
}

function loadNow() {
  clearTimeout(loadTimer);
  loadTimer = null;
  editing = null;
  if (ready) send("load", { source: el.source.value, breakpoints: [...breakpoints], ram_size: Number(el.ramSize.value) });
}

function sourceChanged(immediately) {
  let program = currentProgram();
  if (!program) {
    program = createProgram(`${current.name.replace(/\.asm$/i, "")} copy`, el.source.value, [...breakpoints]);
    current = { kind: "mine", id: program.id };
    store.set("current", current);
    fillProgramList();
  }
  program.source = el.source.value;
  saveProgramsNow();
  renderSource();
  clearTimeout(loadTimer);
  if (immediately) loadNow();
  else loadTimer = setTimeout(loadNow, 400);
}

function downloadProgram() {
  const base = displayName().replace(/\.asm$/i, "").replace(/[\\/:*?"<>|]+/g, "-").trim() || "program";
  const url = URL.createObjectURL(new Blob([el.source.value], { type: "text/plain" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${base}.asm`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---------- Editor ----------
const escapeHtml = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

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
    return `<div class="g-row${hasCode ? " code" : ""}" data-line="${n}" title="${hasCode ? "Toggle breakpoint (F9)" : ""}">` +
      `<span class="bp"></span><span class="no">${n}</span><span class="ad">${hasCode ? hex(address, 4) : ""}</span></div>`;
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
  persistBreakpoints();
  renderMarks();
  renderRom();
  if (ready) send("set_breakpoints", { lines: [...breakpoints] });
}

function caretLine() {
  return el.source.value.slice(0, el.source.selectionStart).split("\n").length;
}

// ---------- Rendering ----------
const hex = (value, width) => value.toString(16).toUpperCase().padStart(width, "0");
const canEdit = () => ready && !running && !!(state && state.program);

function render() {
  renderTransport();
  renderRegisters();
  renderDataPath();
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
  el.back.disabled = !ready || running || !(state && state.history && state.history.size > 0);
  el.lampRun.classList.toggle("on", running);
  el.lampBreak.classList.toggle("on", !running && (status === "break" || status === "paused"));
  el.lampHalt.classList.toggle("on", status === "halted" || (status === "error" && !!(state && state.program)));
  const digits = String(state ? state.cycles : 0);
  el.cycle.innerHTML = `<s>${"0".repeat(Math.max(0, 6 - digits.length))}</s>${digits}`;
}

function editInput(label, width) {
  return `<input class="edit" id="editInput" value="${escapeHtml(editing.text)}" maxlength="${width + 2}" spellcheck="false" autocomplete="off" aria-label="${escapeHtml(label)}">`;
}

function focusEditInput() {
  const input = $("editInput");
  if (input && document.activeElement !== input) {
    input.focus();
    input.select();
  }
}

function renderRegisters() {
  const registers = state ? state.registers : Array(16).fill(0);
  const written = new Set(state && !running ? state.written : []);
  const editable = canEdit();
  const valueHtml = (name, value, width) => {
    if (editing && editing.kind === "reg" && editing.name === name) return editInput(`New value for ${name}`, width);
    return `<span class="hex${editable ? " editable" : ""}" data-edit-reg="${name}"${editable ? ' title="Edit value"' : ""}>${hex(value, width)}</span>`;
  };
  const cards = REGISTER_NAMES.map((name, i) => {
    if (name === "F") return null;
    const value = registers[i];
    const wide = name === "PC" || name === "SP";
    const bits = wide ? "" : `<div class="bits" aria-hidden="true">${Array.from({ length: 8 }, (_, b) =>
      `<i class="${(value >> (7 - b)) & 1 ? "on" : ""}"></i>`).join("")}</div>`;
    return `<div class="reg${written.has(name) ? " changed" : ""}${value === 0 ? " zero" : ""}">` +
      `<div class="top"><span class="name">${name}</span><span class="dec">${value}</span></div>` +
      `${valueHtml(name, value, wide ? 4 : 2)}${bits}</div>`;
  }).filter(Boolean);
  const flags = registers[F];
  cards.push(`<div class="reg${written.has("F") ? " changed" : ""}${flags === 0 ? " zero" : ""}">` +
    `<div class="top"><span class="name">F</span><span class="dec">${flags}</span></div>` +
    `${valueHtml("F", flags, 2)}` +
    `<div class="flags">${FLAGS.map(([f, bit]) => `<span class="flag${flags & bit ? " on" : ""}${editable ? " editable" : ""}" data-flag-bit="${bit}"${editable ? ` title="Flip ${f}"` : ""}><i></i><b>${f}</b></span>`).join("")}</div></div>`);
  el.regs.innerHTML = cards.join("");
  if (editing && editing.kind === "reg") focusEditInput();
}

// ---------- Data path ----------
// A textbook-style datapath: register boxes with write enables, an A bus and a MUX-selected B bus into
// the ALU, function select, flags, and a result bus that feeds registers, RAM and the PC.
const ALU = {};
for (const [name, op] of [["add", "ADD"], ["sub", "SUB"], ["mul", "MUL"], ["div", "DIV"]]) {
  ALU[name] = { op, form: "rr" }; ALU[name + "i"] = { op, form: "ri" }; ALU[name + "a"] = { op, form: "ra" };
}
for (const [name, op] of [["and", "AND"], ["or", "OR"], ["xor", "XOR"]]) {
  ALU[name + "d"] = { op, form: "rr" }; ALU[name + "i"] = { op, form: "ri" }; ALU[name + "a"] = { op, form: "ra" };
}
Object.assign(ALU, {
  cmp: { op: "CMP", form: "rr" }, cmpi: { op: "CMP", form: "ri" }, cmpa: { op: "CMP", form: "ra" },
  inc: { op: "INC", form: "one" }, dec: { op: "DEC", form: "one" },
  rtl: { op: "ROL", form: "r" }, rtr: { op: "ROR", form: "r" }, inv: { op: "NOT", form: "r" }, sar: { op: "SAR", form: "r" },
  shl: { op: "SHL", form: "ri" }, shr: { op: "SHR", form: "ri" },
});
const REGISTER_JUMPS = { jz: "A = 0 ?", jnz: "A ≠ 0 ?", je: "A = B ?", ja: "A > B ?", jae: "A ≥ B ?", jb: "A < B ?", jbe: "A ≤ B ?" };

function datapathModel(next, preview, registers) {
  const m = next.mnemonic;
  const ops = next.operands;
  const writes = preview.registers || {};
  const regSource = (index) => ({ kind: "REG", name: REGISTER_NAMES[index], value: registers[index], width: index >= SP ? 4 : 2 });
  const immediate = (value, width = 2) => ({ kind: "IMM", value, width });
  const memory = (address, width = 2, value = ram[address] ?? 0) => ({ kind: "RAM", address, value, width });
  const targetOperand = ops.find(([kind]) => kind === "a");
  const model = { a: null, b: null, op: null, flagsRead: false, jumpTest: false };

  if (ALU[m]) {
    const { op, form } = ALU[m];
    model.op = op;
    model.a = regSource(ops[0][1]);
    if (form === "rr") model.b = regSource(ops[1][1]);
    else if (form === "ri") model.b = immediate(ops[1][1]);
    else if (form === "ra") model.b = memory(ops[1][1]);
    else if (form === "one") model.b = immediate(1);
  } else if (m in REGISTER_JUMPS) {
    model.op = REGISTER_JUMPS[m];
    model.a = regSource(ops[0][1]);
    model.b = immediate(m === "jz" || m === "jnz" ? 0 : ops[1][1]);
    model.jumpTest = true;
  } else {
    switch (m) {
      case "mov": model.b = regSource(ops[1][1]); model.op = "PASS B"; break;
      case "mvi": model.b = immediate(ops[1][1]); model.op = "PASS B"; break;
      case "ld": model.b = memory(ops[1][1]); model.op = "PASS B"; break;
      case "st": case "push": model.a = regSource(ops[0][1]); model.op = "PASS A"; break;
      case "pushi": model.b = immediate(ops[0][1]); model.op = "PASS B"; break;
      case "pusha": model.b = memory(ops[0][1]); model.op = "PASS B"; break;
      case "pop": model.b = memory(registers[SP]); model.op = "PASS B"; break;
      case "ret": model.b = memory(registers[SP], 4, preview.next_address); model.op = "PASS B"; break;
      case "call": case "jmp": model.b = immediate(targetOperand[1], 4); model.op = "PASS B"; break;
      case "jc": case "jnc":
        model.b = immediate(targetOperand[1], 4);
        model.op = m === "jc" ? "PASS B if C" : "PASS B if not C";
        model.flagsRead = true;
        break;
      default: break; // nop, hlt
    }
  }

  model.destinations = Object.entries(writes).filter(([name]) => name !== "F" && name !== "PC")
    .map(([name, value]) => ({ name, value, width: name === "SP" ? 4 : 2 }));
  model.flags = "F" in writes ? writes.F : null;
  model.ramWrites = preview.ram || [];
  model.pcLoad = preview.jumped ? preview.next_address : null;
  return model;
}

function drawDatapath(model, next, registers) {
  const svg = [];
  const add = (markup) => svg.push(markup);
  const cls = (base, live) => `${base}${live ? " live" : ""}`;
  const arrow = (live) => `marker-end="url(#${live ? "dp-arrow-live" : "dp-arrow"})"`;
  // Buses are plain lines; branches and signals end in a fixed-size arrowhead at a box edge.
  const wire = (d, live, extra = "") => add(`<path class="${cls("wire" + extra, live)}" d="${d}" ${extra.includes("bus") ? "" : arrow(live)}/>`);
  const text = (x, y, className, content, anchor = "start") => add(`<text class="${className}" x="${x}" y="${y}" text-anchor="${anchor}">${escapeHtml(content)}</text>`);
  const value = (v, width) => hex(v, width);
  const idle = !model;

  add(`<defs>
    <marker id="dp-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="11" markerHeight="11" orient="auto"><path class="arrow" d="M0 0 L10 5 L0 10 z"/></marker>
    <marker id="dp-arrow-live" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="11" markerHeight="11" orient="auto"><path class="arrow live" d="M0 0 L10 5 L0 10 z"/></marker>
  </defs>`);

  const pcLoad = !!(model && model.pcLoad !== null);
  const ramWrite = !!(model && model.ramWrites.length);

  // --- Fetch and decode: PC addresses ROM, ROM feeds the decoder ---
  add(`<rect class="${pcLoad ? "box act" : "box"}" x="40" y="16" width="124" height="44" rx="2"/>`);
  text(154, 34, pcLoad ? "bl" : "bl dim", "PC", "end");
  text(48, 34, "bv", value(next ? next.address : registers ? registers[PC] : 0, 4));
  text(48, 52, cls("en", pcLoad), pcLoad ? `load ← ${value(model.pcLoad, 4)}` : "load");
  wire("M164 38 H226", !idle);
  add(`<rect class="${idle ? "box" : "box act"}" x="228" y="16" width="150" height="44" rx="2"/>`);
  text(238, 34, idle ? "bl dim" : "bl", "ROM");
  text(238, 52, "bv", next ? `${value(next.address, 4)}: ${next.bytes.map((b) => hex(b, 2)).join(" ")}` : "");
  wire("M378 38 H438", !idle);
  add(`<rect class="${idle ? "box" : "box act"}" x="440" y="16" width="150" height="44" rx="2"/>`);
  text(450, 34, idle ? "bl dim" : "bl", "DECODER");
  text(450, 52, "bv", next ? `${hex(next.bytes[0], 2)} → ${next.mnemonic}` : "");

  // --- Register column: the registers this instruction reads or writes ---
  const slots = [];
  const slotFor = (name, width, currentValue) => {
    let slot = slots.find((s) => s.name === name);
    if (!slot && slots.length < 4) {
      slot = { name, width, value: currentValue, write: null };
      slots.push(slot);
    }
    return slot;
  };
  if (model) {
    if (model.a && model.a.kind === "REG") slotFor(model.a.name, model.a.width, model.a.value);
    if (model.b && model.b.kind === "REG") slotFor(model.b.name, model.b.width, model.b.value);
    for (const d of model.destinations) {
      const slot = slotFor(d.name, d.width, registers[REGISTER_NAMES.indexOf(d.name)]);
      if (slot) slot.write = d.value;
    }
  }
  if (!slots.length) slots.push({ name: "A", width: 2, value: registers ? registers[0] : 0, write: null });
  const slotY = (i) => 100 + i * 52;
  const slotMid = (i) => slotY(i) + 22;
  const slotIndex = (name) => Math.max(slots.findIndex((s) => s.name === name), 0);

  // Left rail: the result bus rising to register write inputs and the PC load input
  const anyWrite = slots.some((s) => s.write !== null);
  wire("M14 406 V38", anyWrite || pcLoad, " bus");
  wire("M14 38 H38", pcLoad);
  slots.forEach((slot, i) => {
    const written = slot.write !== null;
    const involved = written || !!(model && ((model.a && model.a.name === slot.name) || (model.b && model.b.name === slot.name)));
    wire(`M14 ${slotMid(i)} H38`, written);
    add(`<rect class="${written ? "box act" : involved ? "box read" : "box"}" x="40" y="${slotY(i)}" width="124" height="44" rx="2"/>`);
    text(154, slotY(i) + 18, involved ? "bl" : "bl dim", slot.name, "end");
    text(48, slotY(i) + 18, "bv", value(slot.value, slot.width));
    text(48, slotY(i) + 36, cls("en", written), written ? `write ← ${value(slot.write, slot.width)}` : "write");
  });

  // --- A bus ---
  // Only drawn when the instruction reads a register onto it, so a register that is only written
  // never appears to feed the ALU.
  const aLive = !!(model && model.a);
  if (aLive) {
    wire(`M164 ${slotMid(slotIndex(model.a.name))} H330 V286`, true);
    text(338, 262, "lbl live", "A Bus");
    text(338, 278, "lv", `${model.a.name}=${value(model.a.value, model.a.width)}`);
  }

  // --- MUX selecting the B bus: from a register, the decoder (immediate) or RAM ---
  const bKind = model && model.b ? model.b.kind : null;
  if (bKind === "REG") wire(`M164 ${slotMid(slotIndex(model.b.name))} H206 V156 H488 V186`, true);
  wire("M515 60 V186", bKind === "IMM");

  const ramActive = bKind === "RAM" || ramWrite;
  add(`<rect class="${ramActive ? "box act" : "box"}" x="660" y="96" width="124" height="54" rx="2"/>`);
  text(670, 114, ramActive ? "bl" : "bl dim", "RAM");
  if (ramWrite) {
    const [[address, low], second] = model.ramWrites;
    // call pushes a 16-bit return address as two bytes, low byte first in memory
    const word = second && second[0] === address + 1;
    text(670, 130, "bv hot", `[${value(address, 4)}] ← ${word ? value((second[1] << 8) | low, 4) : value(low, 2)}`);
  } else if (bKind === "RAM") {
    text(670, 130, "bv", `[${value(model.b.address, 4)}] = ${value(model.b.value, model.b.width)}`);
  }
  text(670, 144, cls("en", ramWrite), "write");
  wire("M660 123 H542 V186", bKind === "RAM");

  add(`<polygon class="${bKind ? "box act" : "box"}" points="470,190 560,190 544,236 486,236"/>`);
  [["REG", 488], ["IMM", 515], ["RAM", 542]].forEach(([name, x]) => text(x, 202, cls("mux-in", bKind === name), name, "middle"));
  text(515, 226, bKind ? "bl" : "bl dim", "MUX", "middle");
  wire("M640 214 H556", !!bKind);
  text(644, 212, cls("en", !!bKind), "B Bus select");
  text(644, 226, "lv", bKind || "");

  const bLive = !!bKind;
  wire("M515 236 V286", bLive);
  text(523, 262, cls("lbl", bLive), "B Bus");
  if (bLive) {
    const b = model.b;
    const shown = b.kind === "REG" ? `${b.name}=${value(b.value, b.width)}` : b.kind === "RAM" ? `[${value(b.address, 4)}]=${value(b.value, b.width)}` : value(b.value, b.width);
    text(523, 278, "lv", shown);
  }

  // --- ALU ---
  const aluLive = !!(model && model.op);
  add(`<polygon class="${aluLive ? "box act" : "box"}" points="280,290 390,290 412,312 468,312 490,290 600,290 530,374 350,374"/>`);
  text(440, 356, aluLive ? "bl big" : "bl big dim", "ALU", "middle");
  wire("M680 320 H580", aluLive);
  text(684, 318, cls("en", aluLive), "F  function select");
  text(684, 332, "lv", aluLive ? model.op : "");

  // --- Flags ---
  const flagsLive = !!(model && model.flags !== null);
  const flagsRead = !!(model && model.flagsRead);
  const flagValue = flagsLive ? model.flags : registers ? registers[F] : 0;
  wire("M546 358 H618", flagsLive);
  add(`<rect class="${flagsLive ? "box act" : flagsRead ? "box read" : "box"}" x="620" y="340" width="84" height="40" rx="2"/>`);
  FLAGS.forEach(([letter, bit], i) => {
    const x = 638 + i * 16;
    text(x, 356, "lamp-letter", letter, "middle");
    add(`<circle class="lamp-dot${flagValue & bit ? " on" : ""}" cx="${x}" cy="368" r="4"/>`);
  });
  text(712, 364, flagsLive ? "en live" : "en", "flags");

  // --- Result bus: up the left rail to registers and PC, up the right rail to RAM ---
  const result = !!(model && (model.destinations.length || ramWrite || pcLoad || model.jumpTest));
  wire("M440 374 V400", result);
  wire("M14 406 H806", result, " bus");
  let resultText = "";
  if (model) {
    if (model.jumpTest) resultText = pcLoad ? `taken → ${value(model.pcLoad, 4)}` : "not taken";
    else if (pcLoad) resultText = value(model.pcLoad, 4);
    else if (model.destinations.length) resultText = value(model.destinations[0].value, model.destinations[0].width);
    else if (ramWrite) resultText = value(model.ramWrites[0][1], 2);
  }
  text(450, 396, cls("lbl", result), "Result Bus");
  text(450, 426, "lv", resultText);

  wire("M806 406 V123", ramWrite, " bus");
  wire("M806 123 H786", ramWrite);

  return svg.join("");
}

function renderDataPath() {
  const active = !!(state && state.next && state.preview && !state.preview.error && !running);
  const model = active ? datapathModel(state.next, state.preview, state.registers) : null;
  el.datapath.innerHTML = drawDatapath(model, active ? state.next : null, state ? state.registers : null);

  if (!state || !state.next || running) el.pathMeta.textContent = running ? "running" : "";
  else if (state.preview && state.preview.error) el.pathMeta.textContent = `next stops: ${state.preview.error.split(":")[0]}`;
  else el.pathMeta.textContent = state.next.text;
  el.pathMeta.classList.toggle("bad", !!(state && state.preview && state.preview.error && !running));
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

function dumpRows(bytes, firstRow, rowCount, classify, editable) {
  const head = `<div class="hexrow hexhead"><span></span>${Array.from({ length: 16 }, (_, i) => `<span>${i.toString(16).toUpperCase()}</span>`).join("")}</div>`;
  let html = head;
  for (let row = 0; row < rowCount; row++) {
    const base = firstRow + row * 16;
    if (base >= bytes.length) break;
    let cells = "";
    for (let i = 0; i < 16; i++) {
      const address = base + i;
      if (address >= bytes.length) { cells += "<span></span>"; continue; }
      if (editable && editing && editing.kind === "ram" && editing.address === address) {
        cells += `<span class="editing">${editInput(`New value for RAM ${hex(address, 4)}`, 2)}</span>`;
        continue;
      }
      cells += `<span class="${classify(address)}" data-address="${address}">${hex(bytes[address], 2)}</span>`;
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
  }, true);
  el.ramDump.classList.toggle("editable", canEdit());
  el.memFollow.setAttribute("aria-pressed", String(followSp));
  if (editing && editing.kind === "ram") focusEditInput();

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
        [address === pc ? "pc" : "", breakAddresses.has(address) ? "bpa" : ""].filter(Boolean).join(" "), false)
    : "";
}

function parseNumber(text) {
  const value = text.trim();
  if (/^0x[0-9a-f]+$/i.test(value)) return parseInt(value.slice(2), 16);
  if (/^0b[01]+$/i.test(value)) return parseInt(value.slice(2), 2);
  if (/^0o[0-7]+$/i.test(value)) return parseInt(value.slice(2), 8);
  if (/^\d+$/.test(value)) return Number(value);
  return undefined;
}

function resolveAddress(text) {
  const value = text.trim();
  if (!value) return null;
  if (labelsByName.has(value)) return labelsByName.get(value);
  const number = parseNumber(value);
  if (number !== undefined) return number;
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

// ---------- Editing values ----------
function parseEditValue(text) {
  const value = text.trim();
  if (/^0x[0-9a-f]+$/i.test(value)) return parseInt(value.slice(2), 16);
  if (/^0b[01]+$/i.test(value)) return parseInt(value.slice(2), 2);
  if (/^0d\d+$/i.test(value)) return parseInt(value.slice(2), 10);
  if (/^[0-9a-f]+$/i.test(value)) return parseInt(value, 16); // plain values are hex, as displayed
  return null;
}

function startEdit(target) {
  if (!canEdit()) return;
  editing = target;
  if (target.kind === "reg") renderRegisters(); else renderMemory();
}

function commitEdit() {
  const input = $("editInput");
  if (!input || !editing) return;
  const value = parseEditValue(input.value);
  const max = editing.kind === "reg" && (editing.name === "PC" || editing.name === "SP") ? 0xFFFF : 0xFF;
  if (value === null || value > max) {
    input.setAttribute("aria-invalid", "true");
    return;
  }
  const edit = editing;
  editing = null;
  if (edit.kind === "reg") send("poke_register", { register: edit.name, value });
  else send("poke_ram", { address: edit.address, value });
}

function cancelEdit() {
  if (!editing) return;
  const kind = editing.kind;
  editing = null;
  if (kind === "reg") renderRegisters(); else renderMemory();
}

document.addEventListener("keydown", (event) => {
  if (event.target.id !== "editInput") return;
  if (event.key === "Enter") { event.preventDefault(); commitEdit(); }
  else if (event.key === "Escape") { event.preventDefault(); cancelEdit(); }
});
document.addEventListener("input", (event) => {
  if (event.target.id === "editInput" && editing) {
    editing.text = event.target.value;
    event.target.removeAttribute("aria-invalid");
  }
});
document.addEventListener("focusout", (event) => {
  if (event.target.id === "editInput") setTimeout(() => { if (editing && document.activeElement?.id !== "editInput") cancelEdit(); }, 0);
});

el.regs.addEventListener("click", (event) => {
  if (!canEdit()) return;
  const flag = event.target.closest("[data-flag-bit]");
  if (flag) {
    send("poke_register", { register: "F", value: state.registers[F] ^ Number(flag.dataset.flagBit) });
    return;
  }
  const valueCell = event.target.closest("[data-edit-reg]");
  if (valueCell) {
    const name = valueCell.dataset.editReg;
    const index = REGISTER_NAMES.indexOf(name);
    startEdit({ kind: "reg", name, text: hex(state.registers[index], index >= SP ? 4 : 2) });
  }
});

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
  const rewindFrom = state && state.history && !running ? state.history.rewind_from : null;
  const rows = entries.map((e) => {
    const canRewind = rewindFrom !== null && e.cycle >= rewindFrom && e.cycle <= state.cycles;
    const attrs = canRewind ? ` class="rw" data-rewind="${e.cycle}" title="Rewind to before this instruction"` : "";
    return `<tr${attrs}><td class="c">${e.cycle}</td><td class="a">${hex(e.address, 4)}</td>` +
      `<td class="b">${e.bytes.map((b) => hex(b, 2)).join(" ")}</td><td class="i">${escapeHtml(e.text)}</td>` +
      `<td class="fx">${effectHtml(e.effect)}</td></tr>`;
  });
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
  if (commandError) {
    box.classList.add("bad");
    box.textContent = commandError.charAt(0).toUpperCase() + commandError.slice(1);
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
    const saved = currentProgram() ? "Saved · " : "";
    box.innerHTML = `<span>${saved}Assembled <b>✓</b></span><span>${p.labels} ${p.labels === 1 ? "label" : "labels"} · ${bps} ${bps === 1 ? "breakpoint" : "breakpoints"}</span>`;
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
function doStep() { if (!el.step.disabled) { editing = null; send("step"); } }
function doBack() { if (!el.back.disabled) { editing = null; send("back"); } }
function doRunPause() {
  if (el.run.disabled) return;
  editing = null;
  if (running) send("pause");
  else send("run", clockSetting());
}
function doReset() { if (!el.reset.disabled) { editing = null; send("reset"); } }

el.step.addEventListener("click", doStep);
el.back.addEventListener("click", doBack);
el.run.addEventListener("click", doRunPause);
el.reset.addEventListener("click", doReset);
el.clock.addEventListener("input", clockChanged);
el.ramSize.addEventListener("change", () => {
  store.set("ramSize", el.ramSize.value);
  followSp = true;
  el.memAddress.value = "";
  loadNow();
});

// Programs
el.program.addEventListener("change", () => {
  const [kind, ...rest] = el.program.value.split(":");
  const id = rest.join(":");
  openProgram(kind === "mine" ? { kind: "mine", id } : { kind: "example", name: id });
});
el.progNew.addEventListener("click", async () => {
  const program = createProgram("Untitled", NEW_PROGRAM);
  await openProgram({ kind: "mine", id: program.id });
  el.programName.focus();
  el.programName.select();
});
el.progDuplicate.addEventListener("click", () => {
  const program = createProgram(`${displayName().replace(/\.asm$/i, "")} copy`, el.source.value, [...breakpoints]);
  openProgram({ kind: "mine", id: program.id });
});
el.progDelete.addEventListener("click", () => {
  const program = currentProgram();
  if (!program || !window.confirm(`Delete “${program.name}”? This can't be undone.`)) return;
  programs = programs.filter((p) => p.id !== program.id);
  saveProgramsNow();
  openProgram(programs.length ? { kind: "mine", id: programs[0].id } : { kind: "example", name: DEFAULT_EXAMPLE });
});
el.progDownload.addEventListener("click", downloadProgram);
el.progOpen.addEventListener("click", () => el.progFile.click());
el.progFile.addEventListener("change", async () => {
  const file = el.progFile.files[0];
  el.progFile.value = "";
  if (!file) return;
  const program = createProgram(file.name.replace(/\.[^.]+$/, "") || "Opened program", await file.text());
  openProgram({ kind: "mine", id: program.id });
});
el.programName.addEventListener("change", () => {
  const program = currentProgram();
  if (!program) return;
  const name = el.programName.value.trim();
  if (!name) {
    el.programName.value = program.name;
    return;
  }
  program.name = name;
  saveProgramsNow();
  fillProgramList();
});
el.programName.addEventListener("keydown", (event) => {
  if (event.key === "Enter") el.programName.blur();
  else if (event.key === "Escape") {
    el.programName.value = displayName();
    el.programName.blur();
  }
});

// Editor
el.source.addEventListener("input", () => sourceChanged(false));
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

// Memory
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
el.ramDump.addEventListener("dblclick", (event) => {
  const cell = event.target.closest("[data-address]");
  if (!cell) return;
  const address = Number(cell.dataset.address);
  startEdit({ kind: "ram", address, text: hex(ram[address], 2) });
});

// Trace
el.traceBody.addEventListener("click", (event) => {
  const row = event.target.closest("[data-rewind]");
  if (row && !running) {
    editing = null;
    send("rewind", { cycle: Number(row.dataset.rewind) });
  }
});
for (const button of document.querySelectorAll("[data-trace]")) {
  button.addEventListener("click", () => {
    traceView = button.dataset.trace;
    store.set("traceView", traceView);
    renderTrace();
  });
}

// Sub-tabs: RAM / ROM, and Data path / Trace
function wireTabs(tabs, onChange) {
  for (const [tab] of tabs) {
    $(tab).addEventListener("click", () => {
      for (const [t, pane] of tabs) {
        $(t).setAttribute("aria-selected", String(t === tab));
        $(pane).hidden = t !== tab;
      }
      if (onChange) onChange(tab);
    });
  }
}
wireTabs([["tab-ram", "pane-ram"], ["tab-rom", "pane-rom"]]);
const execTabs = [["tab-path", "pane-path"], ["tab-trace", "pane-trace"]];
function execTabChanged(tab) {
  const trace = tab === "tab-trace";
  el.traceFilters.hidden = !trace;
  el.traceMeta.hidden = !trace;
  el.pathMeta.hidden = trace;
  store.set("execTab", tab);
  if (trace) el.traceScroll.scrollTop = el.traceScroll.scrollHeight;
}
wireTabs(execTabs, execTabChanged);

document.addEventListener("keydown", (event) => {
  if ($("p-console").hidden || event.target.tagName === "INPUT") return;
  if (event.key === "F10") { event.preventDefault(); if (event.shiftKey) doBack(); else doStep(); }
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
  const execTab = store.get("execTab", "tab-path");
  if (execTab === "tab-trace") $("tab-trace").click();
  else execTabChanged("tab-path");

  programs = store.get("programs", null);
  if (!Array.isArray(programs)) {
    // Earlier versions kept one unnamed program; keep it as "My program".
    programs = [];
    const legacySource = store.get("source", null);
    if (legacySource !== null && !store.get("example", DEFAULT_EXAMPLE)) {
      const program = createProgram("My program", legacySource, store.get("breakpoints", []));
      store.set("current", { kind: "mine", id: program.id });
    }
    saveProgramsNow();
  }
  const saved = store.get("current", null);
  const valid = saved && ((saved.kind === "mine" && programs.some((p) => p.id === saved.id)) || (saved.kind === "example" && saved.name));
  await openProgram(valid ? saved : { kind: "example", name: DEFAULT_EXAMPLE });
  render();
}
start();
