# 🚀 Gemini Proxy Service

A lightweight Flask-based proxy service for **Google Gemini API**, designed to help servers in restricted regions (e.g., China, Iran) access Gemini AI through an intermediary server.

---

## 📋 Overview

- **Purpose**: Proxy requests to Google Gemini API from regions where the API is blocked
- **Version**: `1.0.0`
- **Language**: Python 3.12+
- **Framework**: Flask

---

## ✨ Features

- ⚡ **Async/Await Optimization**: 5-10x performance improvement with async HTTP client
- 🔌 **Connection Pooling**: Reuse HTTP connections for better efficiency
- 🚀 **HTTP/2 Support**: Faster requests with multiplexing
- 🔐 **API Key Authentication**: Secure client access with `X-API-KEY` header
- 🌍 **Flexible Model Support**: Use any Gemini/Gemma model (gemini-2.5-flash, gemini-pro, etc.)
- 🔑 **Custom or Default API Keys**: Clients can use their own Gemini key or server's default
- 📊 **Prometheus Metrics**: Monitor requests and performance
- 🛡️ **Security Validations**: Prompt length limits, model validation
- 🐳 **Docker Ready**: Full containerization support

---

## 🔌 API Endpoint

### **POST `/gemini-proxy`**

Proxy a Gemini API request.

**Headers:**

```
X-API-KEY: your_client_api_key
Content-Type: application/json
```

**Request Body:**

```json
{
  "prompt": "What is the capital of France?",
  "model": "gemini-2.5-flash", // optional
  "api_key": "your-gemini-api-key" // optional
}
```

**Rules:**

- ✅ **No model + No key** → Uses server defaults
- ✅ **Custom model + Custom key** → Uses provided values
- ❌ **Custom model + No key** → Error (must provide both)
- ❌ **No model + Custom key** → Error (must provide both)

**Response (Success):**

```json
{
  "result": "OK",
  "data": {
    "response": "The capital of France is Paris.",
    "model": "gemini-2.5-flash",
    "time": 1250
  }
}
```

**Response (Error):**

```json
{
  "result": "Failed",
  "errors": [
    {
      "code": "QUOTA_ERROR",
      "message": "Gemini API quota exceeded. Please try again later."
    }
  ]
}
```

---

## ⚙️ Installation

### **1️⃣ Clone/Copy Project**

```bash
# If this is inside ai-country-detector, move it out first
cd f:\ThucTap
mv ai-country-detector\gemini-proxy-service .\
cd gemini-proxy-service
```

### **2️⃣ Setup Environment**

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your keys
notepad .env
```

**Example `.env`:**

```env
GEMINI_API_KEY=AIzaSyC...your-gemini-key
API_KEYS=client_key_1,client_key_2
PORT=5001
LOG_LEVEL=INFO
FLASK_DEBUG=False
```

### **3️⃣ Install Dependencies**

```bash
pip install -r requirements.txt
```

---

## 🚀 Running the Service

### **Option 1: Local Development**

```bash
python app.py
```

Service runs at: `http://localhost:5001`

**Note**: The service now uses async/await with connection pooling for 5-10x performance improvement!

### **Option 2: Production (Gunicorn with Async Workers) ⭐ Recommended**

For production environments, use Gunicorn with gevent workers for optimal async performance:

```bash
# Install production dependencies
pip install gunicorn gevent

# Run with async workers (recommended)
gunicorn --bind 0.0.0.0:5001 --workers 2 --worker-class gevent --worker-connections 1000 --timeout 30 app:app

# Or with more workers for high traffic
gunicorn --bind 0.0.0.0:5001 --workers 4 --worker-class gevent --worker-connections 1000 --timeout 30 app:app
```

**Gunicorn Configuration Explained:**

- `--workers 2`: Number of worker processes (2-4 recommended)
- `--worker-class gevent`: Use async gevent workers for non-blocking I/O
- `--worker-connections 1000`: Max concurrent connections per worker
- `--timeout 30`: Request timeout (30s for Gemini API calls)

### **Option 3: Docker Compose**

```bash
docker-compose up --build        # Build & run
docker-compose up -d --build     # Run in background
docker-compose logs -f           # View logs
docker-compose down              # Stop
```

---

## 🧪 Testing

### **Health Check**

```bash
curl http://localhost:5001/health
```

### **Proxy Request (No Custom Keys)**

```bash
curl -X POST http://localhost:5001/gemini-proxy \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your_client_key" \
  -d '{
    "prompt": "Explain quantum computing in 3 sentences"
  }'
```

### **Proxy Request (Custom Model + Key)**

```bash
curl -X POST http://localhost:5001/gemini-proxy \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your_client_key" \
  -d '{
    "prompt": "What is AI?",
    "model": "gemini-pro",
    "api_key": "AIzaSyC...custom-gemini-key"
  }'
```

---

## 📊 Monitoring

### **Prometheus Metrics**

Access metrics at: `http://localhost:5001/metrics`

**Available Metrics:**

- `api_requests_total` - Total requests by endpoint and status
- `api_request_duration_seconds` - Request latency histogram

---

## 🔒 Security

- ✅ **API Key validation** for all proxy requests
- ✅ **Prompt length limit**: 10,000 characters max
- ✅ **Model name validation**
- ✅ **CORS protection**
- ✅ **Rate limiting** (via client API keys)

---

## 🛠️ Tech Stack

| Component | Technology              |
| --------- | ----------------------- |
| Framework | Flask 3.x               |
| AI API    | Google Gemini API       |
| Metrics   | Prometheus Client       |
| Container | Docker / Docker Compose |
| Server    | Gunicorn                |
| Python    | 3.12+                   |

---

## 📂 Project Structure

```
gemini-proxy-service/
├── app.py                    # Flask server
├── gemini_proxy_service.py   # Core proxy logic
├── requirements.txt          # Dependencies
├── .env.example              # Config template
├── Dockerfile                # Container image
├── docker-compose.yml        # Docker orchestration
└── README.md                 # This file
```

---

## 🐛 Troubleshooting

| Issue               | Solution                                           |
| ------------------- | -------------------------------------------------- |
| ❌ 401 Unauthorized | Check `X-API-KEY` header matches `.env`            |
| ❌ QUOTA_ERROR      | Gemini API quota exceeded, wait or upgrade plan    |
| ❌ MODEL_NOT_FOUND  | Check model name is valid (gemini-2.5-flash, etc.) |
| ⚠️ Port conflict    | Change `PORT` in `.env`                            |

---

## 📜 License

Copyright © 2025 AIOT Inc.

Developed by AIOT_AI_LAB

---

## 🎯 Use Cases

1. **Geo-Unblocking**: Access Gemini API from restricted regions
2. **Centralized Key Management**: Team shares one server API key
3. **Request Auditing**: Log and monitor all Gemini API usage
4. **Rate Limiting**: Control client access via API keys
