# file_processor/src/routing_lambda/container.py

import os
from dependency_injector import containers, providers

from shared_layer.core_container import CoreContainer
from file_processor.services.impl.routing_service_impl import RoutingServiceImpl
from file_processor.services.routing_service.routing_service import RoutingService
from shared_layer.aws.adapters.dynamodb_adapter import DynamoDBAdapter
from shared_layer.aws.adapters.sqs_adapter import SQSAdapter


class RoutingContainer(CoreContainer):
    """Routing Lambda-specific container, extending core utilities."""

    # ✅ Load Routing Lambda-specific config
    routing_config = providers.Configuration()

    routing_config.from_yaml(
        os.path.join(
            os.path.dirname(__file__),
            "..", "..", "config", "infra_config", "routing_config.yaml"
        )
    )

    # ✅ SQS Adapter
    sqs_adapter = providers.Singleton(
        SQSAdapter,
        config=routing_config,
        sqs_client = CoreContainer.aws_clients.provided.sqs_client
    )

    # ✅ DynamoDB Adapter
    dynamo_repository = providers.Singleton(
        DynamoDBAdapter,
        dynamodb_client=CoreContainer.aws_clients.provided.dynamodb_client,
        config=routing_config
    )

    # ✅ Routing Service Implementation
    # routing_service_impl = providers.Singleton(
    #     RoutingServiceImpl,
    #     dynamo_repository=dynamo_repository,
    #     sqs_adapter=sqs_adapter,
    #     ssm_client=CoreContainer.aws_clients.provided.ssm_client,
    #     config=routing_config
    # )

    # ✅ Bind Interface to Implementation
    routing_service = providers.Singleton(
        RoutingServiceImpl,
        dynamo_repository=dynamo_repository,
        sqs_adapter=sqs_adapter,
        ssm_client=CoreContainer.aws_clients.provided.ssm_client,
        config=routing_config
    )

    #remove loggers from adapters
