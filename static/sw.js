const CACHE_NAME = 'noteforge-v2';
const STATIC_ASSETS = [
    '/',
    '/static/style.css',
    '/static/offline.html',
    '/how-it-works',
    '/about',
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
});

self.addEventListener('fetch', event => {
    // Don't cache POST requests (file uploads)
    if (event.request.method !== 'GET') return;

    event.respondWith(
        caches.match(event.request).then(cached => {
            const fetched = fetch(event.request).then(response => {
                if (response && response.status === 200) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            }).catch(() => {
                // If it's a navigation request, show offline page
                if (event.request.mode === 'navigate') {
                    return caches.match('/static/offline.html');
                }
                return cached;
            });
            return cached || fetched;
        })
    );
});
