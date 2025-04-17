# shared_layer/exception_handler.py


from botocore.exceptions import BotoCoreError, ClientError

from shared_layer.logging.logger import Logger
from shared_layer.model.response import Response

logger = Logger()

class UnrecognizedFileTypeException(Exception):
    def __init__(self, s3_key: str):
        self.s3_key = s3_key
        super().__init__(f"Unrecognized file type: {s3_key}")

class ExceptionHandler:
    @staticmethod
    def handle(context: str, error: Exception, metadata_updater=None, file_metadata=None) -> dict:
        """
        DLQ-friendly centralized exception handler that returns a RoutingResponse DTO as a dict.
        """

        logger.exception(f"❌ [{context}] failed: {str(error)}")

        # Attempt to update metadata status if context is provided
        if metadata_updater and file_metadata:
            try:
                metadata_updater.update_status(file_metadata, "Failed")
            except Exception as e:
                logger.error(f"⚠️ Also failed to update metadata status: {str(e)}", exc_info=True)

        # Return structured RoutingResponse based on exception type
        if isinstance(error, UnrecognizedFileTypeException):
            return Response(
                status="Error",
                context=context,
                message=str(error),
                s3_key=error.s3_key
            ).dict()

        if isinstance(error, ValueError):
            return Response(
                status="Error",
                context=context,
                message=str(error)
            ).dict()

        if isinstance(error, (BotoCoreError, ClientError)):
            return Response(
                status="Error",
                context=context,
                message="AWS service error: " + str(error)
            ).dict()

        return Response(
            status="Error",
            context=context,
            message=str(error)
        ).dict()
