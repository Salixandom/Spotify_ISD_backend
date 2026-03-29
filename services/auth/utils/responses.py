"""
Standard response classes for consistent API responses across all services.

This module provides base classes for success and error responses,
ensuring consistent response formats across all endpoints.
"""

from rest_framework.response import Response
from rest_framework import status
from typing import Any, Dict, Optional


class SuccessResponse(Response):
    """
    Standard success response.

    Usage:
        return SuccessResponse(data={'id': 123}, message='Created successfully')
    """

    def __init__(
        self,
        data: Any = None,
        message: str = "Success",
        status_code: int = status.HTTP_200_OK
    ):
        response_data = {
            'success': True,
            'message': message,
            'data': data if data is not None else {}
        }
        super().__init__(response_data, status=status_code)


class ErrorResponse(Response):
    """
    Standard error response.

    Usage:
        return ErrorResponse(error='not_found', message='Resource not found', status_code=404)
    """

    def __init__(
        self,
        error: str = None,
        message: str = "Error",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict] = None
    ):
        response_data = {
            'success': False,
            'error': error,
            'message': message
        }
        if details:
            response_data['details'] = details
        super().__init__(response_data, status=status_code)


class ValidationErrorResponse(ErrorResponse):
    """
    Validation error response (400).

    Usage:
        return ValidationErrorResponse(errors={'email': 'Invalid email format'})
    """

    def __init__(self, errors: Dict = None, message: str = "Validation failed"):
        super().__init__(
            error='validation_error',
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=errors or {}
        )


class NotFoundResponse(ErrorResponse):
    """
    Not found response (404).

    Usage:
        return NotFoundResponse(message='Playlist not found')
    """

    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            error='not_found',
            message=message,
            status_code=status.HTTP_404_NOT_FOUND
        )


class ForbiddenResponse(ErrorResponse):
    """
    Forbidden response (403).

    Usage:
        return ForbiddenResponse(message='You do not have permission to access this resource')
    """

    def __init__(self, message: str = "Access forbidden"):
        super().__init__(
            error='forbidden',
            message=message,
            status_code=status.HTTP_403_FORBIDDEN
        )


class UnauthorizedResponse(ErrorResponse):
    """
    Unauthorized response (401).

    Usage:
        return UnauthorizedResponse(message='Authentication required')
    """

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            error='unauthorized',
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class ConflictResponse(ErrorResponse):
    """
    Conflict response (409).

    Usage:
        return ConflictResponse(message='Resource already exists')
    """

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(
            error='conflict',
            message=message,
            status_code=status.HTTP_409_CONFLICT
        )


class ServiceUnavailableResponse(ErrorResponse):
    """
    Service unavailable response (503).

    Usage:
        return ServiceUnavailableResponse(message='Service temporarily unavailable')
    """

    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(
            error='service_unavailable',
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
