/**
 * ◑ MiMi Nox – Service Worker
 * 
 * Strategie:
 *   - Static Assets (CSS, JS, fonts, SVG): Cache-First (schnell, offline-fähig)
 *   - API / Images / Audio: Network-Only (immer frisch, kein alter Cache)
 *   - Alles andere: Network-First mit Cache-Fallback
 */

const CACHE_VERSION = 'v6'; // Mobile Telegram-Style Redesign
const CACHE_NAME = `mimi-nox-${CACHE_VERSION}`;

// Statische Assets die pre-gecached werden
const PRECACHE_ASSETS = [
  '/',
  '/index.html',
  '/mobile.html',
  '/style.css',
  '/main.js',
  '/artifact.js',
  '/manifest.json',
  '/forest.svg',
];

// Diese URL-Präfixe werden NIEMALS gecached (immer Live-Daten)
const NETWORK_ONLY_PATTERNS = [
  '/api/',
  '/images/',
  '/audio/',
];

// ── Install: Pre-cache statische Assets ────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_ASSETS))
      .then(() => self.skipWaiting()) // Sofort aktiv werden
  );
});

// ── Activate: Alte Caches löschen ──────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.startsWith('mimi-nox-') && key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

// ── Fetch: Routing-Strategie ────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Network-Only: API, dynamische Daten — niemals cachen
  const isNetworkOnly = NETWORK_ONLY_PATTERNS.some((p) => url.pathname.startsWith(p));
  if (isNetworkOnly) {
    event.respondWith(
      fetch(event.request).catch(() =>
        new Response(
          JSON.stringify({ error: 'offline', message: 'Server nicht erreichbar' }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        )
      )
    );
    return;
  }

  // Cache-First: Statische Assets
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;

      // Nicht im Cache → aus dem Netzwerk holen und cachen
      return fetch(event.request).then((response) => {
        if (response && response.status === 200 && event.request.method === 'GET') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => {
        // Offline-Fallback für HTML-Anfragen
        if (event.request.destination === 'document') {
          return caches.match('/index.html');
        }
        return new Response('', { status: 503 });
      });
    })
  );
});

// ── Message Handler: Cache invalidieren wenn nötig ─────────────────────────
self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
});
