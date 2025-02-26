# app.py
import os
import hashlib
import json
import time
from datetime import datetime, timedelta
import requests
from flask import Flask, request, Response, jsonify
import threading
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache settings
CACHE_DIR = os.environ.get('CACHE_DIR', '/cache')
CACHE_TTL = int(os.environ.get('CACHE_TTL', '600'))  # 10 minutes in seconds
CACHE_CLEANUP_INTERVAL = int(os.environ.get('CACHE_CLEANUP_INTERVAL', '3600'))  # 1 hour

# Server mappings
SERVER_MAPPINGS = {
    'local': 'http://host.docker.internal:5000',      # Local machine
    'network': 'http://192.168.1.100:5000',           # Network machine
    'docker': 'http://flask-container:5000'           # Docker container
}

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

# Create separate directories for different types of cached content
for content_type in ['html', 'json', 'css', 'js', 'other']:
    os.makedirs(os.path.join(CACHE_DIR, content_type), exist_ok=True)

# Cache metadata to track expiration
cache_metadata = {}
cache_lock = threading.Lock()

def generate_cache_key(url, headers=None):
    """Generate a unique cache key for a URL and selected headers"""
    key_parts = [url]
    
    # Include selected headers that might affect response
    if headers:
        for header in ['Accept', 'Accept-Language', 'Accept-Encoding']:
            if header in headers:
                key_parts.append(f"{header}:{headers[header]}")
    
    key_string = '|'.join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()

def get_cache_path(url, content_type=None):
    """Determine the cache file path based on URL and content type"""
    cache_key = generate_cache_key(url, request.headers)
    
    # Determine subdirectory based on content type
    if not content_type:
        content_type = 'other'
    elif 'html' in content_type:
        content_type = 'html'
    elif 'json' in content_type:
        content_type = 'json'
    elif 'css' in content_type:
        content_type = 'css'
    elif 'javascript' in content_type:
        content_type = 'js'
    else:
        content_type = 'other'
    
    return os.path.join(CACHE_DIR, content_type, cache_key)

def is_cache_valid(cache_path):
    """Check if cache is still valid"""
    with cache_lock:
        metadata = cache_metadata.get(cache_path)
        if not metadata:
            return False
        
        return metadata['expires'] > time.time()

def save_to_cache(cache_path, response):
    """Save response to cache"""
    # Create cache directory structure if it doesn't exist
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    
    # Save response data
    cache_data = {
        'status_code': response.status_code,
        'headers': dict(response.headers),
        'content': response.content.decode('utf-8', errors='replace')
    }
    
    with open(cache_path, 'w') as f:
        json.dump(cache_data, f)
    
    # Update metadata
    with cache_lock:
        cache_metadata[cache_path] = {
            'created': time.time(),
            'expires': time.time() + CACHE_TTL,
            'size': len(response.content)
        }

def load_from_cache(cache_path):
    """Load response from cache"""
    try:
        with open(cache_path, 'r') as f:
            cache_data = json.load(f)
        
        # Create response from cached data
        response = Response(
            cache_data['content'],
            status=cache_data['status_code'],
            headers=cache_data['headers']
        )
        
        # Add header to indicate cache hit
        response.headers['X-Cache'] = 'HIT'
        
        return response
    except Exception as e:
        logger.error(f"Error loading from cache: {e}")
        return None

def cleanup_cache():
    """Periodically clean up expired cache entries"""
    while True:
        logger.info("Starting cache cleanup")
        try:
            expired_paths = []
            
            # Identify expired entries
            with cache_lock:
                now = time.time()
                for path, metadata in cache_metadata.items():
                    if metadata['expires'] <= now:
                        expired_paths.append(path)
            
            # Remove expired entries
            for path in expired_paths:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                    with cache_lock:
                        if path in cache_metadata:
                            del cache_metadata[path]
                except Exception as e:
                    logger.error(f"Error removing cache file {path}: {e}")
            
            logger.info(f"Removed {len(expired_paths)} expired cache entries")
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")
        
        # Sleep until next cleanup
        time.sleep(CACHE_CLEANUP_INTERVAL)

@app.route('/<server_type>/<path:path>', methods=['GET'])
def proxy(server_type, path):
    """Proxy requests to backend servers with caching"""
    if server_type not in SERVER_MAPPINGS:
        return jsonify({'error': f"Unknown server type: {server_type}"}), 404
    
    # Skip cache if requested
    skip_cache = request.args.get('nocache', 'false').lower() == 'true'
    
    # Build target URL
    target_url = f"{SERVER_MAPPINGS[server_type]}/{path}"
    if request.query_string:
        target_url += f"?{request.query_string.decode()}"
    
    # Check cache for non-skip requests
    if not skip_cache:
        cache_path = get_cache_path(target_url)
        if os.path.exists(cache_path) and is_cache_valid(cache_path):
            logger.info(f"Cache hit for {target_url}")
            cached_response = load_from_cache(cache_path)
            if cached_response:
                return cached_response
    
    # Forward request to target server
    try:
        logger.info(f"Cache miss for {target_url}")
        response = requests.request(
            method=request.method,
            url=target_url,
            headers={key: value for key, value in request.headers if key != 'Host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            stream=True
        )
        
        # Create flask response from requests response
        flask_response = Response(
            response.content,
            status=response.status_code,
            headers=dict(response.headers)
        )
        
        # Cache successful GET responses
        if not skip_cache and request.method == 'GET' and response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            cache_path = get_cache_path(target_url, content_type)
            save_to_cache(cache_path, response)
            flask_response.headers['X-Cache'] = 'MISS'
        
        return flask_response
    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 500

@app.route('/cache/clear', methods=['POST'])
def clear_cache():
    """Clear the entire cache or specific entries"""
    try:
        # Check if specific URL patterns should be cleared
        patterns = request.json.get('patterns', []) if request.is_json else []
        
        if patterns:
            # Clear specific cache entries matching patterns
            cleared_count = 0
            with cache_lock:
                all_paths = list(cache_metadata.keys())
                for path in all_paths:
                    for pattern in patterns:
                        if pattern in path:
                            if os.path.exists(path):
                                os.remove(path)
                            del cache_metadata[path]
                            cleared_count += 1
                            break
            
            return jsonify({'message': f"Cleared {cleared_count} cache entries matching patterns"}), 200
        else:
            # Clear all cache
            with cache_lock:
                cache_metadata.clear()
            
            for content_type in ['html', 'json', 'css', 'js', 'other']:
                dir_path = os.path.join(CACHE_DIR, content_type)
                for filename in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
            
            return jsonify({'message': "Cache cleared successfully"}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/cache/stats', methods=['GET'])
def cache_stats():
    """Get cache statistics"""
    with cache_lock:
        total_entries = len(cache_metadata)
        total_size = sum(metadata['size'] for metadata in cache_metadata.values())
        
        # Group by content type
        content_types = {}
        for path in cache_metadata:
            content_type = path.split('/')[-2]  # Get content type from path
            if content_type not in content_types:
                content_types[content_type] = 0
            content_types[content_type] += 1
    
    return jsonify({
        'total_entries': total_entries,
        'total_size_bytes': total_size,
        'total_size_mb': round(total_size / (1024 * 1024), 2),
        'content_types': content_types
    }), 200

# Start cache cleanup in a background thread
cleanup_thread = threading.Thread(target=cleanup_cache, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
