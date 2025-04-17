import copy
import os
import logging
from typing import Optional, Mapping, Set, List
from aws_lambda_powertools import Logger as AWSLogger
from aws_lambda_powertools.logging.formatters.datadog import DatadogLogFormatter

from shared_layer.logging.string_util import StringUtil, REDACTED_STR

logger = logging.getLogger(__name__)


class Logger(AWSLogger):
    """
    Custom logging utility class to decouple AWS-related logging code.
    """

    OM_CORRELATION_ID_PATH = 'headers."om-correlation-id" || requestContext.requestId'
    OM_STEPFUNCTION_CORRELATION_ID_PATH = 'parent_execution_name || execution_name'

    def __init__(self, *args, **kwargs):
        location_format = "%(filename)s:%(lineno)d"

        if not kwargs:
            kwargs = {}

        kwargs['log_uncaught_exceptions'] = True

        if not kwargs.get('service') and os.environ.get('om_service_name'):
            kwargs['service'] = os.environ.get('om_service_name')
            os.environ['powertools_service_name'] = os.environ.get('om_service_name')

        kwargs['location'] = location_format
        kwargs['logger_formatter'] = DatadogLogFormatter()

        super().__init__(*args, **kwargs)

    def debug(self, msg: object, *args, redact: bool = False, redact_patterns: List[str] = None,
              redact_keys: Set[str] = None, exc_info=None, stack_info: bool = False,
              stacklevel: int = 3, extra: Optional[Mapping[str, object]] = None, **kwargs):
        if redact and self.isEnabledFor(logging.DEBUG):
            msg = self.redact_message(msg, redact_patterns, redact_keys)
        super().debug(msg, *args, exc_info=exc_info, stack_info=stack_info, stacklevel=stacklevel, extra=extra, **kwargs)

    def info(self, msg: object, *args, redact: bool = False, redact_patterns: List[str] = None,
             redact_keys: Set[str] = None, exc_info=None, stack_info: bool = False,
             stacklevel: int = 3, extra: Optional[Mapping[str, object]] = None, **kwargs):
        if redact and self.isEnabledFor(logging.INFO):
            msg = self.redact_message(msg, redact_patterns, redact_keys)
        super().info(msg, *args, exc_info=exc_info, stack_info=stack_info, stacklevel=stacklevel, extra=extra, **kwargs)

    def error(self, msg: object, *args, redact: bool = False, redact_patterns: List[str] = None,
              redact_keys: Set[str] = None, exc_info=None, stack_info: bool = False,
              stacklevel: int = 3, extra: Optional[Mapping[str, object]] = None, **kwargs):
        if redact and self.isEnabledFor(logging.ERROR):
            msg = self.redact_message(msg, redact_patterns, redact_keys)
        super().error(msg, *args, exc_info=exc_info, stack_info=stack_info, stacklevel=stacklevel, extra=extra, **kwargs)

    def warning(self, msg: object, *args, redact: bool = False, redact_patterns: List[str] = None,
                redact_keys: Set[str] = None, exc_info=None, stack_info: bool = False,
                stacklevel: int = 3, extra: Optional[Mapping[str, object]] = None, **kwargs):
        if redact and self.isEnabledFor(logging.WARNING):
            msg = self.redact_message(msg, redact_patterns, redact_keys)
        super().warning(msg, *args, exc_info=exc_info, stack_info=stack_info, stacklevel=stacklevel, extra=extra, **kwargs)

    @staticmethod
    def redact_message(msg: object, redact_patterns: List[str] = None, redact_keys: Set[str] = None):
        """
        Redacts sensitive information from log messages.
        """
        try:
            if isinstance(msg, dict):
                msg = copy.deepcopy(msg)
                msg = StringUtil.redact_dict(msg, redact_keys)
            elif isinstance(msg, str):
                msg = StringUtil.redact(msg, redact_patterns)
        except Exception as ex:
            msg = REDACTED_STR
            logger.error({"error": "Failed to use custom formatting", "msg": str(ex)})

        return msg
