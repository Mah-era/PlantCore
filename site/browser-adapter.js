/* A local API transport for the GitHub Pages build. No file leaves this browser. */
(() => {
  const worker = new Worker("./python-worker.js");
  const pending = new Map();
  let nextId = 0;
  const nativeFetch = window.fetch.bind(window);

  function bytesToBase64(bytes) {
    let binary = "";
    for (let offset = 0; offset < bytes.length; offset += 32768) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
    }
    return btoa(binary);
  }

  function base64ToBytes(value) {
    const binary = atob(value || "");
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index++) bytes[index] = binary.charCodeAt(index);
    return bytes;
  }

  worker.onmessage = ({ data }) => {
    if (data.type === "progress") {
      const loading = document.querySelector("#content .loading");
      if (loading) loading.textContent = data.message;
      return;
    }
    const task = pending.get(data.id);
    if (!task) return;
    pending.delete(data.id);
    if (data.error) task.reject(new Error(data.error));
    else task.resolve(data.result);
  };
  worker.onerror = (error) => {
    for (const task of pending.values()) task.reject(new Error(error.message));
    pending.clear();
  };

  window.fetch = async (input, options = {}) => {
    const url = typeof input === "string" ? input : input.url;
    if (!url.startsWith("/api/")) return nativeFetch(input, options);
    if (options.signal?.aborted) throw new DOMException("Aborted", "AbortError");
    const rawBody = options.body;
    const body = rawBody instanceof Blob
      ? new Uint8Array(await rawBody.arrayBuffer())
      : rawBody instanceof ArrayBuffer
        ? new Uint8Array(rawBody)
        : new TextEncoder().encode(rawBody || "");
    const id = ++nextId;
    const reply = new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
    worker.postMessage({ id, request: {
      url, method: options.method || "GET", body: bytesToBase64(body),
      contentType: rawBody instanceof Blob ? (rawBody.type || "application/octet-stream") :
        (options.headers?.["Content-Type"] || "application/json"),
    } });
    const result = await reply;
    if (options.signal?.aborted) throw new DOMException("Aborted", "AbortError");
    return new Response(base64ToBytes(result.body), {
      status: result.status,
      headers: Object.fromEntries(result.headers),
    });
  };
})();
