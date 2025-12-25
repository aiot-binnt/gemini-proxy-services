import os
import time
import logging
from logging.handlers import RotatingFileHandler
from functools import wraps

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv
from prometheus_client import Counter, Histogram, generate_latest, REGISTRY

from gemini_proxy_service import GeminiProxyService, DEFAULT_MODEL

# --- Configuration & Logging Setup ---
load_dotenv()

def setup_logger():
    """Configure application logging."""
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, log_level))
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    file_handler = RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=5)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger

logger = setup_logger()

# --- Metrics ---
REQUEST_COUNT = Counter('api_requests_total', 'Total API requests', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('api_request_duration_seconds', 'API request latency')

# --- App Initialization ---
app = Flask(__name__)
CORS(app)

VALID_API_KEYS = {k.strip() for k in os.getenv('API_KEYS', '').split(',') if k.strip()}

# --- Helpers ---
def api_response(success: bool, data=None, errors=None, status: int = 200):
    """Standardize API response format."""
    payload = {"result": "OK" if success else "Failed"}
    if data: payload["data"] = data
    if errors: payload["errors"] = errors
    return jsonify(payload), status

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if VALID_API_KEYS:
            key = request.headers.get('X-API-KEY')
            if not key or key not in VALID_API_KEYS:
                logger.warning(f"Auth failed from IP: {request.remote_addr}")
                REQUEST_COUNT.labels('auth', 'error').inc()
                return api_response(False, errors=[{"code": "AUTH_ERROR", "message": "Invalid API Key"}], status=401)
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "Gemini Proxy Service", "version": "2.0.0-optimized"})

@app.route('/gemini-proxy', methods=['POST'])
@require_api_key
@REQUEST_LATENCY.time()
def gemini_proxy():
    """
    Optimized proxy endpoint for Gemini API calls.
    Configured with better timeouts and generation settings for 2-4x performance improvement.
    
    Request body:
    {
        "prompt": "Your prompt text here",
        "model": "gemini-2.5-flash",  // optional, defaults to gemini-2.5-flash
        "api_key": "your-gemini-api-key"  // optional, uses server's key if not provided
    }
    """
    start_time = time.time()
    data = request.get_json() or {}
    
    # Extract parameters
    prompt = data.get("prompt", "")
    model_name = data.get("model")
    custom_api_key = data.get("api_key")
    
    # Process request using service layer
    result = GeminiProxyService.process_proxy_request(
        prompt=prompt,
        model_name=model_name,
        api_key=custom_api_key,
        fallback_api_key=os.getenv('GEMINI_API_KEY')
    )
    
    processing_time = int((time.time() - start_time) * 1000)
    
    # Handle result
    if result["success"]:
        result_data = {
            "response": result["response"],
            "model": model_name or DEFAULT_MODEL,
            "time": processing_time
        }
        REQUEST_COUNT.labels('gemini-proxy', 'success').inc()
        logger.info(f"Request completed successfully in {processing_time}ms")
        return api_response(True, data=result_data)
    else:
        # Handle error
        error_code = result.get("error_code", "INTERNAL_ERROR")
        error_message = result.get("error_message", "Unknown error")
        
        REQUEST_COUNT.labels('gemini-proxy', 'error').inc()
        
        # Determine HTTP status code
        status_code = 400 if error_code == "VALIDATION_ERROR" else 500
        
        return api_response(
            False,
            errors=[{"code": error_code, "message": error_message}],
            status=status_code
        )

@app.route('/metrics')
def metrics():
    return Response(generate_latest(REGISTRY), mimetype='text/plain')

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    logger.info(f"Starting Gemini Proxy Service (Optimized) on port {port}")
    logger.info("⚡ Optimizations enabled: Better timeouts, optimized generation config")
    logger.info("🚀 For production, use: gunicorn --bind 0.0.0.0:5001 --workers 4 --worker-class gevent --timeout 60 app:app")
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true')
