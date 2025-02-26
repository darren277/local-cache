const CACHE_VERSION = 'v1';
const CACHE_NAME = `local-server-cache-${CACHE_VERSION}`;
const CACHE_TTL = 10 * 60 * 1000; // 10 minutes in milliseconds

// Server patterns to cache - customize these URLs
const SERVER_PATTERNS = [
    "*://localhost:*/",
    "*://127.0.0.1:*/",
    "*://192.168.1.100:*/"
];
  
// Cached content types
const CACHEABLE_CONTENT_TYPES = [
    'text/html',
    'text/css',
    'application/javascript',
    'application/json',
    'image/png',
    'image/jpeg',
    'image/svg+xml'
];
  
// Cache storage
let cacheStorage = {};
  
// Initialize cache from storage
browser.storage.local.get('cacheStorage').then(result => {
    if (result.cacheStorage) {
        cacheStorage = result.cacheStorage;
        cleanExpiredCache();
    }
});
  
// Listen for requests
browser.webRequest.onBeforeRequest.addListener(handleRequest, { urls: SERVER_PATTERNS }, ["blocking"]);
  
function handleRequest(details) {
    // Skip non-GET requests
    if (details.method !== 'GET') {return {};}
  
    // Check for cache bypass parameters
    const url = new URL(details.url);
    if (url.searchParams.has('nocache') || url.searchParams.has('cache_bypass')) {return {};}
  
    const cacheKey = details.url;
    const cachedResponse = cacheStorage[cacheKey];
  
    // If we have a valid cache entry
    if (cachedResponse && !isCacheExpired(cachedResponse)) {
        console.log(`Cache hit for ${cacheKey}`);
        return { redirectUrl: `data:${cachedResponse.contentType};base64,${cachedResponse.data}` };
    }
  
    // Otherwise, proceed with the request
    return {};
}
  
// Listen for responses to cache them
browser.webRequest.onCompleted.addListener(handleResponse, { urls: SERVER_PATTERNS });
  
function handleResponse(details) {
    // Only cache GET requests with success status
    if (details.method !== 'GET' || details.statusCode !== 200) {return;}
  
    const cacheKey = details.url;
    
    // Fetch the response to cache it
    fetch(details.url)
        .then(response => {
            // Check if content type is cacheable
            const contentType = response.headers.get('content-type');
            if (!contentType || !CACHEABLE_CONTENT_TYPES.some(type => contentType.includes(type))) {return;}

            // Get the response data
            return response.arrayBuffer().then(buffer => {
                // Convert to base64
                const data = arrayBufferToBase64(buffer);

                // Store in cache
                cacheStorage[cacheKey] = {data, contentType, timestamp: Date.now()};

                // Save to storage
                browser.storage.local.set({ cacheStorage });
                console.log(`Cached response for ${cacheKey}`);
            });
        })
        .catch(error => {
            console.error(`Error caching response for ${cacheKey}:`, error);
        });
}
  
// Helper to check if cache entry is expired
function isCacheExpired(cacheEntry) {return Date.now() - cacheEntry.timestamp > CACHE_TTL;}
  
// Helper to remove expired cache entries
function cleanExpiredCache() {
    const now = Date.now();
    let hasChanges = false;
    
    Object.keys(cacheStorage).forEach(key => {
        if (now - cacheStorage[key].timestamp > CACHE_TTL) {
            delete cacheStorage[key];
            hasChanges = true;
        }
    });
    
    if (hasChanges) {browser.storage.local.set({ cacheStorage });}
}
  
// Helper to convert ArrayBuffer to base64
function arrayBufferToBase64(buffer) {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;

    for (let i = 0; i < len; i++) {binary += String.fromCharCode(bytes[i]);}

    return btoa(binary);
}
  
// Periodically clean expired cache entries
setInterval(cleanExpiredCache, 5 * 60 * 1000); // Every 5 minutes
