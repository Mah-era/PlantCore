/* Run the same FastAPI application in a browser Web Worker through Pyodide. */
const PYODIDE_VERSION = "0.28.3";
const PYODIDE_ROOT = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
const DATABASE_NAME = "plantcore-browser-runtime";
const DATABASE_STORE = "files";
let runtime;
let sequence = Promise.resolve();

function postProgress(message) {
  self.postMessage({ type: "progress", message });
}

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(DATABASE_STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function readDatabase() {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(DATABASE_STORE, "readonly");
    const request = transaction.objectStore(DATABASE_STORE).get("platform.db");
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => reject(request.error);
    transaction.oncomplete = () => database.close();
  });
}

async function saveDatabase(bytes) {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(DATABASE_STORE, "readwrite");
    transaction.objectStore(DATABASE_STORE).put(bytes, "platform.db");
    transaction.oncomplete = () => { database.close(); resolve(); };
    transaction.onerror = () => { database.close(); reject(transaction.error); };
  });
}

async function initialize() {
  postProgress("Loading the Python planning engine…");
  importScripts(`${PYODIDE_ROOT}pyodide.js`);
  const pyodide = await loadPyodide({ indexURL: PYODIDE_ROOT });
  postProgress("Loading analysis and import libraries…");
  await pyodide.loadPackage(["pydantic", "micropip", "sqlite3"]);
  await pyodide.runPythonAsync("import micropip; await micropip.install(['fastapi==0.115.12', 'openpyxl==3.1.5'])");
  pyodide.FS.mkdirTree("/plantcore/app");
  pyodide.FS.mkdirTree("/plantcore/test-files");
  pyodide.FS.mkdirTree("/plantcore/examples");
  pyodide.FS.mkdirTree("/plantcore/web");
  // The scenario filenames come from the bundle manifest generated at build time.
  const bundleVersion = self.location.search;
  const manifestResponse = await fetch(`./py/manifest.json${bundleVersion}`);
  if (!manifestResponse.ok) throw new Error("Python bundle manifest is missing");
  const manifest = await manifestResponse.json();
  await Promise.all(manifest.map(async (file) => {
    const response = await fetch(`./py/${file}${bundleVersion}`);
    if (!response.ok) throw new Error(`Python bundle file is missing: ${file}`);
    pyodide.FS.writeFile(`/plantcore/${file}`, new Uint8Array(await response.arrayBuffer()));
  }));
  const stored = await readDatabase();
  if (stored) {
    pyodide.FS.mkdirTree("/plantcore/data");
    pyodide.FS.writeFile("/plantcore/data/platform.db", new Uint8Array(stored));
  }
  postProgress("Starting the connected operational model…");
  await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, '/plantcore')
import anyio.to_thread
async def browser_run_sync(function, *args, **kwargs):
    return function(*args, **kwargs)
anyio.to_thread.run_sync = browser_run_sync
import starlette.concurrency
starlette.concurrency.run_in_threadpool = browser_run_sync
import fastapi.routing
fastapi.routing.run_in_threadpool = browser_run_sync
import fastapi.dependencies.utils
fastapi.dependencies.utils.run_in_threadpool = browser_run_sync
from app.main import app
from app import store
store.initialize()
import base64
import traceback
from urllib.parse import urlsplit

async def browser_request(request):
    url = urlsplit(request['url'])
    body = base64.b64decode(request.get('body', ''))
    headers = [(b'host', b'plantcore.github.io')]
    content_type = request.get('contentType')
    if content_type:
        headers.append((b'content-type', content_type.encode()))
    scope = {
        'type': 'http', 'asgi': {'version': '3.0'},
        'http_version': '1.1', 'method': request.get('method', 'GET'),
        'scheme': 'https', 'path': url.path, 'raw_path': url.path.encode(),
        'query_string': url.query.encode(), 'root_path': '',
        'headers': headers, 'client': ('browser', 0),
        'server': ('plantcore.github.io', 443),
    }
    messages = []
    received = False
    async def receive():
        nonlocal received
        if not received:
            received = True
            return {'type': 'http.request', 'body': body, 'more_body': False}
        return {'type': 'http.disconnect'}
    async def send(message):
        messages.append(message)
    try:
        await app(scope, receive, send)
        start = next(x for x in messages if x['type'] == 'http.response.start')
        response_body = b''.join(x.get('body', b'') for x in messages if x['type'] == 'http.response.body')
        return {
            'status': start['status'],
            'headers': [(k.decode(), v.decode()) for k, v in start.get('headers', [])],
            'body': base64.b64encode(response_body).decode(),
        }
    except Exception as exc:
        traceback.print_exc()
        return {'status': 500, 'headers': [('content-type', 'application/json')],
                'body': base64.b64encode(__import__('json').dumps({'detail': str(exc)}).encode()).decode()}
`);
  postProgress("PlantCore is ready.");
  return pyodide;
}

self.onmessage = ({ data }) => {
  sequence = sequence.then(() => handleMessage(data)).catch((error) => {
    self.postMessage({ id: data.id, error: String(error?.message || error) });
  });
};

async function handleMessage(data) {
  const { id, request } = data;
  try {
    runtime ||= initialize();
    const pyodide = await runtime;
    pyodide.globals.set("browser_input", request);
    const proxy = await pyodide.runPythonAsync("await browser_request(browser_input.to_py())");
    const result = proxy.toJs({ dict_converter: Object.fromEntries });
    proxy.destroy();
    if (!["GET", "HEAD"].includes(request.method) && result.status < 400) {
      await saveDatabase(pyodide.FS.readFile("/plantcore/data/platform.db"));
    }
    self.postMessage({ id, result });
  } catch (error) {
    self.postMessage({ id, error: String(error?.message || error) });
  }
}
