import os

from dependency_injector import providers

from file_processor.data_formatters.data_formatter import DataFormatter
from file_processor.data_formatters.processors.csv.csv_processor import CSVProcessor
from file_processor.data_formatters.processors.text.spacy_processor import SpacyProcessor
from file_processor.data_formatters.processors.text.txt_processor import TXTProcessor
from file_processor.services.impl.worker_service_impl import WorkerServiceImpl
from shared_layer.aws.adapters.aoss_adapter import AOSSAdapter
from shared_layer.aws.adapters.bedrock_adapter import BedrockEmbeddingAdapter
from shared_layer.aws.adapters.dynamodb_adapter import DynamoDBAdapter
from shared_layer.aws.adapters.s3_adapter import S3Adapter
from shared_layer.core_container import CoreContainer
from shared_layer.logging.logger import Logger

logger = Logger()  # Logger instance for logging

class SalesWorkerContainer(CoreContainer):
    """Sales Worker Lambda-specific container, extending service utilities."""
    sales_config = providers.Configuration()
    # Load configuration
    sales_config.from_yaml(os.path.join(os.path.dirname(__file__),'..','..','..','config', 'processing_lambdas_config', 'sales_config.yaml'))
    logger.info("Loaded Config:", sales_config())
    # ✅ Sales-Specific Dependencies
    s3_adapter = providers.Singleton(
        S3Adapter,
        config=sales_config
    )
    bedrock_adapter = providers.Singleton(
        BedrockEmbeddingAdapter,
        bedrock_client=CoreContainer.aws_clients.provided.bedrock_client,
        config=sales_config,
    )
    bedrock_repository = bedrock_adapter
    # Add SpacyProcessor provider
    spacy_processor = providers.Factory(
        SpacyProcessor,
        s3_adapter=s3_adapter
    )
    data_formatter = providers.Factory(
        DataFormatter,
        s3_adapter=s3_adapter
    )
    csv_formatter = providers.Factory(
        CSVProcessor,
        s3_adapter=s3_adapter
    )
    txt_processor = providers.Factory(
        TXTProcessor,
        bedrock_repository=bedrock_repository,
        spacy_processor =spacy_processor,
        s3_adapter=s3_adapter
    )

    aoss_adapter = providers.Singleton(
        AOSSAdapter,
        aoss_client=CoreContainer.aws_clients.provided.aoss_client,
        config=sales_config,
    )
    # Bind the abstract AOSSRepository to the concrete AOSSAdapter
    aoss_repository = aoss_adapter  # 👈 This replaces the previous instantiation
    dynamo_repository = providers.Singleton(
        DynamoDBAdapter,
        dynamodb_client=CoreContainer.aws_clients.provided.dynamodb_client,
        config=sales_config
    )

    # ✅ Register the actual implementation
    worker_service = providers.Singleton(
        WorkerServiceImpl,
        s3_adapter=s3_adapter,
        dynamo_repository=dynamo_repository,
        aoss_repository=aoss_repository,
        config=sales_config
    )
