from typing import List, Any, Dict, Optional, Union
from pydantic import ValidationError

class OmInsightsError(Exception):
    """
    Base error for Om Insights platform.
    """
    pass

class OmInsightsPartialSuccessError(OmInsightsError):
    """
    Error wrapper for partial failures.
    """
    def __init__(self, data, source_exception: Exception, message="Partial failure"):
        self.data = data
        self.source_exception = source_exception
        self.message = message
        super().__init__(self.message)

class Base4XXError(OmInsightsError):
    """
    Base 4XX error class for the Om Insights platform.
    """
    def __init__(self, errors: Optional[List[Any]], message, is_custom_error=False, exclude_errors=False, error_code="4000"):
        self._message = message
        self._errors = errors
        self._is_custom_error = is_custom_error
        self._exclude_errors = exclude_errors
        self._error_code = error_code
        super().__init__(message)

    @property
    def message(self) -> str:
        return self._message

    @property
    def errors(self) -> List[Any]:
        return self._errors

    def error_response(self) -> Dict[str, Any]:
        response = {
            "message": self._message,
            "error_code": self._error_code,
        }
        if not self._exclude_errors:
            response["errors"] = self._errors
        return response

    def to_dict(self) -> Any:
        if self._is_custom_error:
            return self._errors
        return self.error_response()

class NotFoundError(Base4XXError):
    """
    Resource not found error (404).
    """
    STATUS_CODE = 404

    def __init__(self, errors=None, message="Requested resource not found."):
        super().__init__(errors, message)

    def error_response(self):
        return {"message": self._message}

class BadRequestError(Base4XXError):
    """
    Bad request error (400).
    """
    STATUS_CODE = 400

    @staticmethod
    def format_error(error):
        return {
            "loc": error["loc"],
            "msg": error["msg"],
            "type": error["type"],
            "input": error.get("input")
        }

    def __init__(self, errors: Union[ValidationError, List[Any]], message="Bad request", is_custom_error=False, error_code="4000"):
        if isinstance(errors, ValidationError):
            errors = [self.format_error(error) for error in errors.errors()]
        super().__init__(errors, message, is_custom_error, error_code=error_code)

class TooManyRequestsError(Base4XXError):
    """
    Too Many Requests Error (429).
    """
    STATUS_CODE = 429
    DEFAULT_MESSAGE = "Too many requests"

    def __init__(self, errors: List[Any], message=DEFAULT_MESSAGE, is_custom_error=False, exclude_errors=True):
        super().__init__(errors, message, is_custom_error, exclude_errors)

class UnauthorizedError(Base4XXError):
    """
    Unauthorized error (401).
    """
    STATUS_CODE = 401

    def __init__(self, errors: Any = None, message="Unauthorized", is_custom_error=False, exclude_errors=True):
        super().__init__(errors, message, is_custom_error, exclude_errors)

class UnprocessableEntityError(Base4XXError):
    """
    Error for Invalid data in the request (422).
    """
    STATUS_CODE = 422

    def __init__(self, errors: Any, message="The given data was invalid.", is_custom_error=False):
        super().__init__(errors, message, is_custom_error)

class ConflictError(Base4XXError):
    """
    Conflict error (409).
    """
    STATUS_CODE = 409

    def __init__(self, errors: List[Any], message="The given data was invalid.", is_custom_error=False):
        super().__init__(errors, message, is_custom_error)

class ForbiddenError(Base4XXError):
    """
    Forbidden error (403).
    """
    STATUS_CODE = 403

    def __init__(self, message="User does not have access.", is_custom_error=False):
        super().__init__(None, message, is_custom_error)

class Base5XXError(OmInsightsError):
    """
    Base 5XX error class for the Om Insights platform.
    """
    def __init__(self, errors: Optional[List[Any]], message, is_custom_error=False):
        self._message = message
        self._errors = errors
        self._is_custom_error = is_custom_error
        super().__init__(message)

    @property
    def message(self) -> str:
        return self._message

    @property
    def errors(self) -> List[Any]:
        return self._errors

    def error_response(self) -> Dict[str, Any]:
        return {
            "message": self._message,
            "errors": self._errors
        }

    def to_dict(self) -> Any:
        if self._is_custom_error:
            return self._errors
        return self.error_response()

class InternalServerError(Base5XXError):
    """
    Internal Server Error (500).
    """
    STATUS_CODE = 500

    def __init__(self, errors: List[Any], message="Internal server error.", is_custom_error=False):
        super().__init__(errors, message, is_custom_error)

class BadGatewayError(Base5XXError):
    """
    Bad Gateway Error (502).
    """
    STATUS_CODE = 502

    def __init__(self, errors: List[Any], message="Bad gateway error.", is_custom_error=False):
        super().__init__(errors, message, is_custom_error)

class GatewayTimeout(Base5XXError):
    """
    Gateway Timeout (504).
    """
    STATUS_CODE = 504

    def __init__(self, errors: List[Any], message="Gateway timeout.", is_custom_error=False):
        super().__init__(errors, message, is_custom_error)

# file_processor/om_core/exceptions.py

# file_processor/om_core/exceptions.py

class OmniInsightsException(Exception):
    """Base Exception for Omni Insights with additional debugging details."""

    def __init__(self, message, file_name=None, business_region=None, company=None, s3_key=None, error_code=None):
        """
        Initialize an exception with additional debugging details.

        :param message: Error message.
        :param file_name: Name of the file that caused the error (optional).
        :param business_region: Business region (optional).
        :param company: Company name (optional).
        :param s3_key: Full S3 path of the file (optional).
        :param error_code: Optional error code for classification.
        """
        self.file_name = file_name
        self.business_region = business_region
        self.company = company
        self.s3_key = s3_key
        self.error_code = error_code
        super().__init__(self.format_message(message))

    def format_message(self, message):
        """Formats the error message to include extra debugging context."""
        details = [message]
        if self.error_code:
            details.append(f"Error Code: {self.error_code}")
        if self.file_name:
            details.append(f"File: {self.file_name}")
        if self.business_region:
            details.append(f"Region: {self.business_region}")
        if self.company:
            details.append(f"Company: {self.company}")
        if self.s3_key:
            details.append(f"S3 Path: {self.s3_key}")
        return " | ".join(details)


class InvalidS3EventException(OmniInsightsException):
    """Raised when an S3 event format is invalid."""
    pass

class MetadataExtractionException(OmniInsightsException):
    """Raised when metadata extraction from the S3 event fails."""
    pass

class QueueProcessingException(OmniInsightsException):
    """Raised when there is an error processing the queue."""
    pass

class AWSBatchSubmissionException(OmniInsightsException):
    """Raised when AWS Batch job submission fails."""
    pass

class LambdaExecutionException(OmniInsightsException):
    """Raised when a Lambda function encounters an unexpected error."""
    pass

HTTP_ERRORS_CLASS_MAP = {
    BadRequestError.STATUS_CODE: BadRequestError,
    ForbiddenError.STATUS_CODE: ForbiddenError,
    NotFoundError.STATUS_CODE: NotFoundError,
    UnprocessableEntityError.STATUS_CODE: UnprocessableEntityError,
    ConflictError.STATUS_CODE: ConflictError,
    InternalServerError.STATUS_CODE: InternalServerError,
    GatewayTimeout.STATUS_CODE: GatewayTimeout,
    BadGatewayError.STATUS_CODE: BadGatewayError,
    UnauthorizedError.STATUS_CODE: UnauthorizedError,
    TooManyRequestsError.STATUS_CODE: TooManyRequestsError,
}
