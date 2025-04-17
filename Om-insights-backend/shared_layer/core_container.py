import os
from dependency_injector import containers, providers
from shared_layer.logging.logger import Logger
from shared_layer.aws.adapters.sqs_adapter import SQSAdapter
from shared_layer.aws_clients import AWSClientProvider
from shared_layer.aws.adapters.dynamodb_adapter import DynamoDBAdapter# 🔹 NEW: Dedicated AWS Clients Module

class CoreContainer(containers.DeclarativeContainer):
    """Core dependency container providing shared utilities and services."""

    # ✅ Common Config (Shared across all Lambdas)
    common_config = providers.Configuration()

    # Load common configurations
    common_config.from_yaml(os.path.join(os.path.dirname(__file__), '..', 'config', 'common_config.yaml'))

    # ✅ Shared Logger
    logger = providers.Singleton(Logger)

    # ✅ AWS Clients (Managed via `AWSClientProvider`)
    aws_clients = providers.Singleton(AWSClientProvider, config=common_config)

    # ✅ SQS Adapter (For async messaging)
    sqs_adapter = providers.Singleton(
        SQSAdapter,
        config=common_config,
        logger=logger
    )

    dynamo_repository = providers.Singleton(
        DynamoDBAdapter, profile_name="Haswanth"
    )