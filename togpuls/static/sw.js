// togpuls service worker
// Cache-first for the app shell so it installs and opens offline.
// Network-first for /api/* so live data stays fresh when online,
// with a tiny offline fallback so the UI doesn't crash if the network drops.

const CACHE = "togpuls-shell-v2";
const SHELL = [
  "/",
  "/static/styles.css",
  "/static/app.js",
  "/static/manifest.webmanifest",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/api/")) {
    // Network-first: try the network, fall back to a tiny offline stub.
    event.respondWith(
      fetch(request).catch(() => new Response(
        JSON.stringify({ error: "offline", detail: "Ingen nettverkstilkobling." }),
        { status: 503, headers: { "Content-Type": "application/json" } }
      ))
    );
    return;
  }

  // Network-first for the shell + static assets: always fresh when online
  // (no more stale HTML/CSS/JS after a deploy), with the cache as an offline
  // fallback. Filenames aren't hashed, so cache-first would serve stale assets.
  event.respondWith(
    fetch(request)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(request, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() => caches.match(request))
  );
});
