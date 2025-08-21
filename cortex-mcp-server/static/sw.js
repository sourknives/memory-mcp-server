/**
 * Service Worker for Cortex MCP Enhanced Web Interface
 * Provides advanced offline functionality, intelligent caching, and performance optimization
 */

const CACHE_NAME = 'cortex-mcp-v2';
const STATIC_CACHE = 'cortex-static-v2';
const DYNAMIC_CACHE = 'cortex-dynamic-v2';
const API_CACHE = 'cortex-api-v2';

const STATIC_ASSETS = [
    '/ui',
    '/static/css/styles.css',
    '/static/js/utils.js',
    '/static/js/api.js',
    '/static/js/ui.js',
    '/static/js/app.js'
];

const API_CACHE_PATTERNS = [
    /\/health$/,
    /\/stats$/,
    /\/projects$/,
    /\/preferences$/,
    /\/monitoring\//
];

const CACHE_STRATEGIES = {
    CACHE_FIRST: 'cache-first',
    NETWORK_FIRST: 'network-first',
    STALE_WHILE_REVALIDATE: 'stale-while-revalidate',
    NETWORK_ONLY: 'network-only',
    CACHE_ONLY: 'cache-only'
};

// Install event - cache static assets with versioning
self.addEventListener('install', (event) => {
    console.log('Service Worker installing...');
    
    event.waitUntil(
        Promise.all([
            // Cache static assets
            caches.open(STATIC_CACHE).then((cache) => {
                console.log('Caching static assets...');
                return cache.addAll(STATIC_ASSETS);
            }),
            // Initialize other caches
            caches.open(DYNAMIC_CACHE),
            caches.open(API_CACHE)
        ])
        .then(() => {
            console.log('All caches initialized successfully');
            return self.skipWaiting();
        })
        .catch((error) => {
            console.error('Failed to initialize caches:', error);
        })
    );
});

// Activate event - clean up old caches and manage cache versions
self.addEventListener('activate', (event) => {
    console.log('Service Worker activating...');
    
    const expectedCaches = [STATIC_CACHE, DYNAMIC_CACHE, API_CACHE];
    
    event.waitUntil(
        Promise.all([
            // Clean up old caches
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => {
                        if (!expectedCaches.includes(cacheName)) {
                            console.log('Deleting old cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            }),
            // Claim all clients
            self.clients.claim()
        ])
        .then(() => {
            console.log('Service Worker activated and caches cleaned');
        })
    );
});

// Fetch event - intelligent caching strategies
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Only handle GET requests for caching
    if (request.method !== 'GET') {
        return;
    }
    
    // Determine caching strategy based on request type
    const strategy = getCachingStrategy(url, request);
    
    switch (strategy) {
        case CACHE_STRATEGIES.CACHE_FIRST:
            event.respondWith(cacheFirst(request));
            break;
        case CACHE_STRATEGIES.NETWORK_FIRST:
            event.respondWith(networkFirst(request));
            break;
        case CACHE_STRATEGIES.STALE_WHILE_REVALIDATE:
            event.respondWith(staleWhileRevalidate(request));
            break;
        case CACHE_STRATEGIES.NETWORK_ONLY:
            event.respondWith(fetch(request));
            break;
        case CACHE_STRATEGIES.CACHE_ONLY:
            event.respondWith(caches.match(request));
            break;
        default:
            event.respondWith(networkFirst(request));
    }
});

/**
 * Determine caching strategy based on request
 * @param {URL} url - Request URL
 * @param {Request} request - Request object
 * @returns {string} Caching strategy
 */
function getCachingStrategy(url, request) {
    // Static assets - cache first
    if (url.pathname.startsWith('/static/') || url.pathname === '/ui') {
        return CACHE_STRATEGIES.CACHE_FIRST;
    }
    
    // API endpoints that can be cached
    if (API_CACHE_PATTERNS.some(pattern => pattern.test(url.pathname))) {
        return CACHE_STRATEGIES.STALE_WHILE_REVALIDATE;
    }
    
    // Write operations - network only
    if (request.method !== 'GET') {
        return CACHE_STRATEGIES.NETWORK_ONLY;
    }
    
    // Default to network first
    return CACHE_STRATEGIES.NETWORK_FIRST;
}

/**
 * Cache first strategy
 * @param {Request} request - Request object
 * @returns {Promise<Response>} Response promise
 */
async function cacheFirst(request) {
    try {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        const networkResponse = await fetch(request);
        if (networkResponse.status === 200) {
            const cache = await caches.open(STATIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        console.error('Cache first strategy failed:', error);
        return createOfflineResponse(request);
    }
}

/**
 * Network first strategy
 * @param {Request} request - Request object
 * @returns {Promise<Response>} Response promise
 */
async function networkFirst(request) {
    try {
        const networkResponse = await fetch(request);
        
        // Cache successful responses
        if (networkResponse.status === 200) {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('Network failed, trying cache:', error.message);
        
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        return createOfflineResponse(request);
    }
}

/**
 * Stale while revalidate strategy
 * @param {Request} request - Request object
 * @returns {Promise<Response>} Response promise
 */
async function staleWhileRevalidate(request) {
    const cachedResponse = await caches.match(request);
    
    // Start network request in background
    const networkResponsePromise = fetch(request)
        .then(async (networkResponse) => {
            if (networkResponse.status === 200) {
                const cache = await caches.open(API_CACHE);
                cache.put(request, networkResponse.clone());
            }
            return networkResponse;
        })
        .catch((error) => {
            console.log('Background revalidation failed:', error.message);
        });
    
    // Return cached response immediately if available
    if (cachedResponse) {
        // Don't await the network request
        networkResponsePromise;
        return cachedResponse;
    }
    
    // If no cache, wait for network
    try {
        return await networkResponsePromise;
    } catch (error) {
        return createOfflineResponse(request);
    }
}

/**
 * Create offline response
 * @param {Request} request - Request object
 * @returns {Response} Offline response
 */
function createOfflineResponse(request) {
    const url = new URL(request.url);
    
    // API endpoints
    if (url.pathname.startsWith('/api') || 
        url.pathname.startsWith('/health') || 
        url.pathname.startsWith('/stats')) {
        return new Response(
            JSON.stringify({
                success: false,
                error: 'Offline - API unavailable',
                offline: true,
                timestamp: new Date().toISOString()
            }),
            {
                status: 503,
                statusText: 'Service Unavailable',
                headers: { 
                    'Content-Type': 'application/json',
                    'Cache-Control': 'no-cache'
                }
            }
        );
    }
    
    // HTML pages
    if (request.headers.get('accept')?.includes('text/html')) {
        return new Response(
            `
            <!DOCTYPE html>
            <html>
            <head>
                <title>Offline - Cortex MCP</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                    .offline-message { max-width: 400px; margin: 0 auto; }
                    .retry-btn { 
                        background: #007bff; color: white; border: none; 
                        padding: 10px 20px; border-radius: 5px; cursor: pointer; 
                    }
                </style>
            </head>
            <body>
                <div class="offline-message">
                    <h1>🔌 You're Offline</h1>
                    <p>Please check your internet connection and try again.</p>
                    <button class="retry-btn" onclick="window.location.reload()">
                        Retry
                    </button>
                </div>
            </body>
            </html>
            `,
            {
                status: 503,
                statusText: 'Service Unavailable',
                headers: { 
                    'Content-Type': 'text/html',
                    'Cache-Control': 'no-cache'
                }
            }
        );
    }
    
    // Default offline response
    return new Response(
        'Offline - Please check your connection',
        { 
            status: 503,
            statusText: 'Service Unavailable',
            headers: { 
                'Content-Type': 'text/plain',
                'Cache-Control': 'no-cache'
            }
        }
    );
}

// Handle background sync (if supported)
if ('sync' in self.registration) {
    self.addEventListener('sync', (event) => {
        console.log('Background sync triggered:', event.tag);
        
        if (event.tag === 'background-sync') {
            event.waitUntil(
                // Perform background sync operations
                Promise.resolve()
            );
        }
    });
}

// Handle push notifications (if supported)
if ('push' in self.registration) {
    self.addEventListener('push', (event) => {
        console.log('Push notification received:', event);
        
        const options = {
            body: event.data ? event.data.text() : 'New notification from Cortex MCP',
            icon: '/static/icons/icon-192x192.png',
            badge: '/static/icons/badge-72x72.png',
            tag: 'cortex-notification',
            requireInteraction: false
        };
        
        event.waitUntil(
            self.registration.showNotification('Cortex MCP', options)
        );
    });
}

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
    console.log('Notification clicked:', event);
    
    event.notification.close();
    
    event.waitUntil(
        self.clients.openWindow('/ui')
    );
});

console.log('Service Worker loaded successfully');