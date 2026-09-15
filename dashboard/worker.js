// Runs the Python emulator (src/) in Pyodide, off the page's main thread.
// Messages in:  {type: "load" | "step" | "reset" | "set_breakpoints" | "run" | "pause" | "rate", args}
// Messages out: {type: "ready", python, examples} | {type: "result", running, state, trace, stopped, clear_trace}
//               | {type: "fatal", message}

let session = null;
let running = false;
let rate = 12;          // instructions per second
let maxSpeed = false;
let owed = 0;           // fractional instructions carried between ticks
let lastTick = 0;
let lastPost = 0;
let timer = null;

const post = (message) => self.postMessage(message);
const call = (command) => JSON.parse(session.handle(JSON.stringify(command)));

async function fetchText(url) {
  const response = await fetch(url);
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
      setRate(args);
      running = true;
      owed = 0;
      lastTick = performance.now();
      schedule(0);
      return;
    case "rate":
      setRate(args);
      return;
    case "pause":
      stop();
      send("state");
      return;
    case "set_breakpoints":
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
  if (timer !== null) clearTimeout(timer);
  timer = null;
}

function schedule(delay) {
  timer = setTimeout(tick, delay);
}

function tick() {
  timer = null;
  if (!running) return;
  const now = performance.now();
  let steps;
  if (maxSpeed) {
    steps = 25000;
  } else {
    owed = Math.min(owed + (rate * (now - lastTick)) / 1000, rate); // at most one second of backlog
    steps = Math.floor(owed);
    owed -= steps;
  }
  lastTick = now;

  if (steps > 0) {
    const result = call({ command: "run", max_steps: steps });
    if (result.stopped) running = false;
    // At full speed, update the page at most ~60 times per second; always report a stop.
    if (!maxSpeed || result.stopped || now - lastPost > 16) {
      post({ type: "result", running, ...result });
      lastPost = now;
    }
  }
  if (running) schedule(maxSpeed ? 0 : 16);
}
