// popup.js
document.addEventListener('DOMContentLoaded', function() {
    // Update stats
    updateStats();
    
    // Clear cache button
    document.getElementById('clearCache').addEventListener('click', function() {
        browser.storage.local.set({ cacheStorage: {} });
        updateStats();
    });
});

function updateStats() {
    browser.storage.local.get('cacheStorage').then(result => {
        const cache = result.cacheStorage || {};
        const itemCount = Object.keys(cache).length;

        // Calculate size in KB
        let totalSize = 0;
        Object.values(cache).forEach(item => {
            totalSize += item.data.length * 0.75; // Approximate base64 size
        });

        document.getElementById('itemCount').textContent = itemCount;
        document.getElementById('storageSize').textContent = (totalSize / 1024).toFixed(2);
    });
}