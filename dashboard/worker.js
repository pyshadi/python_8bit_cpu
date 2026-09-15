// Runs the Python emulator (src/) in Pyodide, off the page's main thread.
// Messages in:  {type: "load" | "step" | "reset" | "set_breakpoints" | "run" | "pause" | "rate" | "compile" | ..., args}
// Messages out: {type: "ready", python, examples} | {type: "result", running, state, trace, stopped, clear_trace}
//               | {type: "compiled", seq, compiled, compile_error} | {type: "fatal", message}

let session = null;
let running = false;
let rate = 12;          // instructions per second
let maxSpeed = false;
let owed = 0;           // fractional instructions carried between ticks
let lastTick = 0;
let lastPost = 0;
let nextFrameAt = 0;    // when a program's next `frame` may start, at full speed
const FRAME_MS = 1000 / 30;
// Runs happen in short chunks so Pause and key presses, which wait for the current chunk, take effect at once
const CHUNK_MS = 12;
let stepsPerMs = 20;    // measured emulator speed, used to size the chunks
let timer = null;
let loopId = 0;         // bumped by stop(), so ticks scheduled by an earlier run never fire

const post = (message) => self.postMessage(message);
const call = (command) => JSON.parse(session.handle(JSON.stringify(command)));

async function fetchText(url) {
  // Revalidate every time so the manifest and Python files always match the deployed dashboard,
  // even while the browser still has older copies cached (unchanged files come back as a cheap 304).
  const response = await fetch(url, { cache: "no-cache" });
  if (!response.ok) throw new Error(`could not load ${url} (${response.status})`);
  return response.text();
}

const ready = (async () => {
  const manifest = JSON.parse(await fetchText("manifest.json"));
  const base = `https://cdn.jsdelivr.net/pyodide/v${manifest.pyodide}/full/`;
  importScripts(base + "pyodide.js");
  const pyodide = await loadPyodide({ indexURL: base });

  pyodide.FS.mkdirTree("/app/src");
  const sources = await Promise.all(manifest.python.map((name) => fetchText(`../src/${name}`)));
  manifest.python.forEach((name, i) => pyodide.FS.writeFile(`/app/src/${name}`, sources[i]));

  pyodide.runPython('import sys\nsys.path.insert(0, "/app")\nfrom src.session import Session\nsession = Session()');
  session = pyodide.globals.get("session");
  post({ type: "ready", python: pyodide.runPython("import platform; platform.python_version()"), examples: manifest.examples });
})();

ready.catch((error) => post({ type: "fatal", message: String((error && error.message) || error) }));

let queue = Promise.resolve();
self.onmessage = (event) => {
  queue = queue.then(() => ready).then(() => handle(event.data)).catch(() => {});
};

function handle({ type, args = {} }) {
  switch (type) {
    case "run":
      stop();
      setRate(args);
      running = true;
      owed = 0;
      lastTick = performance.now();
      nextFrameAt = lastTick;
      schedule(0);
      return;
    case "rate":
      setRate(args);
      return;
    case "pause":
      stop();
      send("state");
      return;
    case "compile": // C to assembly; the machine is untouched and keeps running
      post({ type: "compiled", seq: args.seq, ...call({ command: "compile", source: args.source, ram_size: args.ram_size }) });
      return;
    case "set_breakpoints":
    case "set_keys":
      send(type, args);
      return;
    default: // load, step, reset
      stop();
      send(type, args);
  }
}

function send(command, args = {}) {
  post({ type: "result", running, ...call({ command, ...args }) });
}

function setRate({ rate: perSecond, max }) {
  if (typeof perSecond === "number") rate = perSecond;
  maxSpeed = Boolean(max);
}

function stop() {
  running = false;
  loopId++;
  if (timer !== null) clearTimeout(timer);
  timer = null;
}

// A zero delay uses a message to ourselves: it lets queued messages (like Pause) in first, without
// the minimum delay browsers add to repeated setTimeout(0)
const yieldChannel = new MessageChannel();
yieldChannel.port1.onmessage = ({ data }) => { if (data === loopId) tick(); };

function schedule(delay) {
  const id = loopId;
  if (delay <= 0) yieldChannel.port2.postMessage(id);
  else timer = setTimeout(() => { timer = null; if (id === loopId) tick(); }, delay);
}

function tick() {
  if (!running) return;
  const now = performance.now();
  const chunk = Math.max(50, Math.min(25000, Math.round(stepsPerMs * CHUNK_MS)));
  let steps;
  if (maxSpeed) {
    steps = chunk;
  } else {
    owed = Math.min(owed + (rate * (now - lastTick)) / 1000, rate); // at most one second of backlog
    steps = Math.min(Math.floor(owed), chunk);
    owed -= steps;
  }
  lastTick = now;

  let waitForFrame = 0;
  if (steps > 0) {
    // At full speed, update the page at most ~60 times per second. Runs in between are "quiet":
    // Python skips building the state, and keeps their trace for the next update.
    // At full speed a program's `frame` instruction also paces it to 30 frames per second.
    const update = !maxSpeed || now - lastPost > 16;
    const started = performance.now();
    const outcome = call({ command: "run", max_steps: steps, quiet: !update, stop_at_frame: maxSpeed });
    const elapsed = performance.now() - started;
    if (!update && !outcome.frame && !outcome.stopped && elapsed > 1) {
      stepsPerMs = stepsPerMs * 0.7 + (steps / elapsed) * 0.3;
    }
    if (outcome.stopped) running = false;
    if (update || outcome.stopped || outcome.frame) {
      post({ type: "result", running, ...(update ? outcome : call({ command: "state" })) });
      lastPost = now;
    }
    if (outcome.frame) {
      nextFrameAt = Math.max(nextFrameAt + FRAME_MS, now);
      waitForFrame = Math.max(0, nextFrameAt - performance.now());
    }
  }
  if (running) schedule(maxSpeed ? waitForFrame : 16);
}
