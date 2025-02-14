import time
import logging
import json
from typing import Any, Dict
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware:
    """Middleware to log all requests and responses"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Log request
        request_data = {
            'method': request.method,
            'path': request.path,
            'user': str(request.user) if hasattr(request, 'user') else 'anonymous',
            'timestamp': datetime.now().isoformat()
        }
        
        # Add request body for non-GET requests
        if request.method not in ['GET', 'HEAD']:
            try:
                request_data['body'] = json.loads(request.body)
            except Exception:
                request_data['body'] = str(request.body)
        
        logger.info(f"Incoming request: {json.dumps(request_data)}")
        
        # Process request
        response = self.get_response(request)
        
        # Log response
        response_data = {
            'status_code': response.status_code,
            'path': request.path,
            'method': request.method,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Outgoing response: {json.dumps(response_data)}")
        
        return response


class ErrorHandlingMiddleware:
    """Middleware to handle errors and exceptions"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        return self.get_response(request)
    
    def process_exception(self, request, exception):
        """Handle various types of exceptions and return appropriate responses"""
        
        if isinstance(exception, ValidationError):
            return JsonResponse({
                'error': 'Validation Error',
                'detail': exception.detail
            }, status=400)
            
        elif isinstance(exception, PermissionDenied):
            return JsonResponse({
                'error': 'Permission Denied',
                'detail': 'You do not have permission to perform this action'
            }, status=403)
            
        elif isinstance(exception, Exception):
            # Log the error
            logger.error(f"Unhandled exception: {str(exception)}", exc_info=True)
            
            # In development, return detailed error
            if settings.DEBUG:
                return JsonResponse({
                    'error': str(exception.__class__.__name__),
                    'detail': str(exception)
                }, status=500)
            
            # In production, return generic error
            return JsonResponse({
                'error': 'Internal Server Error',
                'detail': 'An unexpected error occurred'
            }, status=500)


class APIVersionMiddleware:
    """Middleware to handle API versioning"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Check if it's an API request
        if request.path.startswith('/api/'):
            # Get version from header or default to v1
            version = request.headers.get('X-API-Version', 'v1')
            
            # Validate version
            if version not in ['v1']:  # Add new versions here
                return JsonResponse({
                    'error': 'Invalid API Version',
                    'detail': f'Version {version} is not supported'
                }, status=400)
            
            # Add version to request for use in views
            request.api_version = version
        
        return self.get_response(request)


class PerformanceMonitoringMiddleware:
    """Middleware to monitor request performance"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Start timer
        start_time = time.time()
        
        # Process request
        response = self.get_response(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log performance metrics
        performance_data = {
            'path': request.path,
            'method': request.method,
            'duration': duration,
            'status_code': response.status_code
        }
        
        logger.info(f"Performance metrics: {json.dumps(performance_data)}")
        
        # Add timing header to response
        response['X-Request-Duration'] = str(duration)
        
        return response


class RateLimitingMiddleware:
    """Middleware to implement rate limiting"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limit = getattr(settings, 'API_RATE_LIMIT', 100)  # requests per minute
        self.rate_limit_period = 60  # seconds
        
    def get_client_ip(self, request: HttpRequest) -> str:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
        
    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path.startswith('/api/'):
            client_ip = self.get_client_ip(request)
            cache_key = f'rate_limit_{client_ip}'
            
            # Get current request count
            requests = cache.get(cache_key, {'count': 0, 'reset_time': time.time()})
            
            # Reset count if period has expired
            current_time = time.time()
            if current_time - requests['reset_time'] > self.rate_limit_period:
                requests = {'count': 0, 'reset_time': current_time}
            
            # Increment request count
            requests['count'] += 1
            
            # Update cache
            cache.set(cache_key, requests, self.rate_limit_period)
            
            # Check if rate limit exceeded
            if requests['count'] > self.rate_limit:
                return JsonResponse({
                    'error': 'Rate Limit Exceeded',
                    'detail': f'Maximum {self.rate_limit} requests per minute allowed'
                }, status=429)
            
            # Add rate limit headers
            response = self.get_response(request)
            response['X-RateLimit-Limit'] = str(self.rate_limit)
            response['X-RateLimit-Remaining'] = str(self.rate_limit - requests['count'])
            response['X-RateLimit-Reset'] = str(int(requests['reset_time'] + self.rate_limit_period))
            
            return response
            
        return self.get_response(request) 