"""
Gemini Proxy Service - Vertex AI Version
Handles proxy requests to Google Vertex AI Gemini API with service account authentication.
"""

import os
import logging
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from typing import Dict, Any, Optional
from google.api_core.exceptions import (
    GoogleAPIError, 
    ResourceExhausted, 
    PermissionDenied,
    InvalidArgument,
    DeadlineExceeded,
    ServiceUnavailable,
    Unauthenticated
)

logger = logging.getLogger(__name__)

# Configuration
MAX_PROMPT_LENGTH = 10000
DEFAULT_MODEL = "gemini-2.0-flash-exp"

# Error code to HTTP status code mapping
ERROR_HTTP_STATUS = {
    "AUTH_ERROR": 401,
    "CREDENTIALS_ERROR": 401,
    "PERMISSION_DENIED": 403,
    "BILLING_DISABLED": 403,
    "VALIDATION_ERROR": 400,
    "CONTENT_SAFETY_ERROR": 400,
    "MODEL_NOT_FOUND": 404,
    "QUOTA_ERROR": 429,
    "RATE_LIMIT_ERROR": 429,
    "TIMEOUT_ERROR": 504,
    "NETWORK_ERROR": 502,
    "SERVICE_UNAVAILABLE": 503,
    "CONFIG_ERROR": 500,
    "API_ERROR": 500,
    "INTERNAL_ERROR": 500,
}

# Initialize Vertex AI once when module loads
_vertex_ai_initialized = False
_vertex_ai_init_error = None

try:
    project = os.getenv('GOOGLE_CLOUD_PROJECT')
    location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
    
    if not project:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable is required")
    
    vertexai.init(project=project, location=location)
    _vertex_ai_initialized = True
    logger.info(f"Vertex AI initialized: project={project}, location={location}")
except Exception as e:
    _vertex_ai_init_error = str(e)
    logger.error(f"Failed to initialize Vertex AI: {_vertex_ai_init_error}")
    logger.error("Service will not be able to process requests until this is fixed!")

# Configure transport optimizations
import google.auth.transport.requests
import requests as requests_lib

# Create a session with connection pooling
_session = None

def get_optimized_session():
    """Get or create an optimized requests session with connection pooling."""
    global _session
    if _session is None:
        _session = requests_lib.Session()
        # Configure connection pooling
        adapter = requests_lib.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=2,
            pool_block=False
        )
        _session.mount('http://', adapter)
        _session.mount('https://', adapter)
    return _session


class GeminiProxyService:
    """Service to handle Gemini API proxy requests with optimized configuration."""
    
    @staticmethod
    def validate_model(model_name: str) -> tuple[bool, Optional[str]]:
        """Validate model name format."""
        if not model_name:
            return False, "Model name is required"
        if len(model_name.strip()) < 3:
            return False, "Invalid model name format"
        return True, None
    
    @staticmethod
    def validate_prompt(prompt: str) -> tuple[bool, Optional[str]]:
        """Validate prompt for security and length."""
        if not prompt or not prompt.strip():
            return False, "Prompt is required"
        if len(prompt) > MAX_PROMPT_LENGTH:
            return False, f"Prompt too long. Maximum {MAX_PROMPT_LENGTH} characters allowed"
        return True, None
    

    @staticmethod
    def call_gemini_api(
        prompt: str,
        model_name: str
    ) -> Dict[str, Any]:
        """
        Call Vertex AI Gemini API with optimized configuration and error handling.
        Uses service account authentication configured via environment variables.
        
        Args:
            prompt: The prompt text
            model_name: The model to use
            
        Returns:
            Dict with 'success', 'response' (if success), 'error_code', 'error_message'
        """
        try:
            # Check if Vertex AI was initialized successfully
            if not _vertex_ai_initialized:
                return {
                    "success": False,
                    "error_code": "CONFIG_ERROR",
                    "error_message": "Vertex AI initialization failed",
                    "details": _vertex_ai_init_error or "Unknown initialization error",
                    "action": "Check GOOGLE_CLOUD_PROJECT and GOOGLE_APPLICATION_CREDENTIALS environment variables"
                }
            
            # Create generation config
            generation_config = GenerationConfig(
                temperature=0.7,
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,
            )
            
            # Create model instance with Vertex AI
            model = GenerativeModel(
                model_name=model_name,
                generation_config=generation_config
            )
            
            # Generate content
            logger.info(f"Calling Vertex AI Gemini: model={model_name}, prompt_length={len(prompt)}")
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # Extract response text and clean it
            response_text = response.text if hasattr(response, 'text') else str(response)
            response_text = response_text.strip()
            
            # Validate response is not empty
            if not response_text:
                logger.warning("Received empty response from Vertex AI")
                return {
                    "success": False,
                    "error_code": "API_ERROR",
                    "error_message": "Received empty response from Vertex AI",
                    "action": "Try rephrasing your prompt or use a different model"
                }
            
            return {
                "success": True,
                "response": response_text
            }
            
        except ResourceExhausted as e:
            logger.warning(f"Vertex AI quota exhausted: {str(e)}")
            return {
                "success": False,
                "error_code": "QUOTA_ERROR",
                "error_message": "Vertex AI quota exceeded. Please try again later.",
                "action": "Wait a few minutes or check quota limits in Google Cloud Console",
                "help_url": f"https://console.cloud.google.com/apis/api/aiplatform.googleapis.com/quotas?project={os.getenv('GOOGLE_CLOUD_PROJECT')}"
            }
        
        except InvalidArgument as e:
            logger.error(f"Invalid argument: {str(e)}")
            error_msg = str(e)
            
            # Check for content safety violations
            if "safety" in error_msg.lower() or "block" in error_msg.lower():
                return {
                    "success": False,
                    "error_code": "CONTENT_SAFETY_ERROR",
                    "error_message": "Content was blocked by safety filters",
                    "details": "Your prompt may contain inappropriate content",
                    "action": "Modify your prompt to comply with content safety guidelines"
                }
            
            return {
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "error_message": f"Invalid request: {error_msg}",
                "action": "Check your prompt and model parameters"
            }
        
        except DeadlineExceeded as e:
            logger.error(f"Request timeout: {str(e)}")
            return {
                "success": False,
                "error_code": "TIMEOUT_ERROR",
                "error_message": "Request timed out",
                "details": "The API request took too long to complete",
                "action": "Try again with a shorter prompt or simpler request"
            }
        
        except ServiceUnavailable as e:
            logger.error(f"Service unavailable: {str(e)}")
            return {
                "success": False,
                "error_code": "SERVICE_UNAVAILABLE",
                "error_message": "Vertex AI service is temporarily unavailable",
                "action": "Please try again in a few moments"
            }
        
        except Unauthenticated as e:
            logger.error(f"Authentication failed: {str(e)}")
            return {
                "success": False,
                "error_code": "CREDENTIALS_ERROR",
                "error_message": "Invalid or expired service account credentials",
                "details": str(e),
                "action": "Verify GOOGLE_APPLICATION_CREDENTIALS points to a valid service account JSON key"
            }
            
        except PermissionDenied as e:
            logger.error(f"Vertex AI permission denied: {str(e)}")
            error_msg = str(e)
            project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
            
            # Check if it's a billing issue
            if "billing" in error_msg.lower() and "disabled" in error_msg.lower():
                return {
                    "success": False,
                    "error_code": "BILLING_DISABLED",
                    "error_message": "Billing is not enabled for this Google Cloud project",
                    "details": "Vertex AI requires an active billing account",
                    "action": "Enable billing in Google Cloud Console",
                    "help_url": f"https://console.cloud.google.com/billing/enable?project={project_id}"
                }
            
            # Regular permission denied
            return {
                "success": False,
                "error_code": "PERMISSION_DENIED",
                "error_message": "Service account lacks required permissions",
                "details": error_msg,
                "action": "Grant 'Vertex AI User' role to your service account in IAM",
                "help_url": f"https://console.cloud.google.com/iam-admin/iam?project={project_id}"
            }
            
        except GoogleAPIError as e:
            logger.error(f"Vertex AI API error: {str(e)}")
            error_msg = str(e)
            
            # Model not found
            if "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
                return {
                    "success": False,
                    "error_code": "MODEL_NOT_FOUND",
                    "error_message": f"Model '{model_name}' not found or not accessible in Vertex AI",
                    "action": "Check model name spelling and availability in your region",
                    "help_url": "https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models"
                }
            
            # Rate limit (different from quota)
            if "rate" in error_msg.lower() and "limit" in error_msg.lower():
                return {
                    "success": False,
                    "error_code": "RATE_LIMIT_ERROR",
                    "error_message": "Rate limit exceeded",
                    "details": "Too many requests in a short time",
                    "action": "Wait a moment and retry with exponential backoff"
                }
            
            # Generic API error
            return {
                "success": False,
                "error_code": "API_ERROR",
                "error_message": "Vertex AI API error occurred",
                "details": error_msg
            }
            
        except Exception as e:
            logger.error(f"Unexpected error calling Vertex AI: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error_code": "INTERNAL_ERROR",
                "error_message": "An unexpected internal error occurred",
                "details": str(e),
                "action": "Check application logs for more details"
            }
    
    @classmethod
    def process_proxy_request(
        cls,
        prompt: str,
        model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a complete proxy request with all validations.
        Uses service account authentication configured via environment variables.
        
        Args:
            prompt: The prompt text
            model_name: Optional model name (defaults to DEFAULT_MODEL)
            
        Returns:
            Dict with 'success', 'response' or 'error_code', 'error_message'
        """
        # Use default model if not provided
        model = (model_name or DEFAULT_MODEL).strip()
        
        # Validate prompt
        valid_prompt, prompt_error = cls.validate_prompt(prompt)
        if not valid_prompt:
            return {
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "error_message": prompt_error
            }
        
        # Validate model
        valid_model, model_error = cls.validate_model(model)
        if not valid_model:
            return {
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "error_message": model_error
            }
        
        # Verify Vertex AI is configured
        if not os.getenv('GOOGLE_CLOUD_PROJECT'):
            return {
                "success": False,
                "error_code": "CONFIG_ERROR",
                "error_message": "GOOGLE_CLOUD_PROJECT environment variable is required for Vertex AI authentication"
            }
        
        # Call Vertex AI Gemini API
        result = cls.call_gemini_api(prompt, model)
        
        return result
