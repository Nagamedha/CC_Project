# Future processors
# from file_processor.utils.processors.txt_processor import TXTProcessor
# from file_processor.utils.processors.pdf_processor import PDFProcessor

from file_processor.data_formatters.processor_factory import ProcessorFactory
from typing import Dict, Any, Optional

from file_processor.model.workers_model import ProcessingContext
from shared_layer.aws.adapters.s3_adapter import S3Adapter
from shared_layer.logging.logger import Logger
from dependency_injector.wiring import Provide

logger = Logger()  # Logger instance for logging

class DataFormatter:
    """Handles different file formats and routes them to appropriate processors."""
    def __init__(self,s3_adapter: S3Adapter= Provide['s3_adapter']):
        self.s3_adapter = s3_adapter

    @staticmethod
    def process_file(context: ProcessingContext) -> Dict[str, Any]:
        """
        Process a file from S3 based on its format type.

        Args:
            context: context for processing, metadata

        Returns:
            Processed data as a dictionary

        Raises:
            ValueError: If no processor is available for the given format
            Exception: If processing fails
        """
        try:
            # Get the appropriate processor using the factory
            processor = ProcessorFactory.get_processor(context.file_format)
            # Process the file
            logger.info(f"Processing {context.file_key} from {context.bucket_name} with {context.file_format} processor")
            processed_data = processor.process(context)
            return processed_data

        except ValueError as e:
            logger.error(f"Processor error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error processing file {context.file_key} from {context.bucket_name}: {str(e)}")
            raise
