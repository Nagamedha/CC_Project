import json

from dependency_injector.wiring import inject
from file_processor.model.workers_model import SQSMessage
from shared_layer.logging.logger import Logger

from file_processor.src.processing_lambdas.container_factory import create_container
from file_processor.src.processing_lambdas.sales.container import SalesWorkerContainer
from pydantic import ValidationError


# ✅ Factory function for initializing the container

# ✅ Initialize the container globally (for dependency injection wiring)
container = create_container(SalesWorkerContainer)

# ✅ Use centralized logger
logger = container.logger()

# ✅ Wire the container for dependency injection
container.wire(modules=[__name__])

@logger.inject_lambda_context(correlation_id_path=Logger.OM_CORRELATION_ID_PATH)
@inject
def lambda_handler(event, context):
    """Sales Processing Lambda Handler"""

    # ✅ Initialize the container inside the handler
    container = create_container(SalesWorkerContainer)

    # ✅ Resolve the Sales Processor Service explicitly
    sales_processor_service = container.worker_service()

    try:
        logger.info("✅ Sales Processing Lambda Invoked.")

        # ✅ Validate SQS Event
        if "Records" not in event or not event["Records"]:
            raise ValueError("Invalid SQS Event: No Records found.")

        # ✅ Parse SQS Message
        try:
            sqs_body = json.loads(event["Records"][0]["body"])
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid SQS message format: {e}")

        logger.info(f"📩 Received SQS Message: {json.dumps(sqs_body, indent=2)}")

        # ✅ Validate message format using Pydantic
        try:
            validated_sqs_body = SQSMessage(**sqs_body)
            logger.info(f"✅ SQS Message validated: {validated_sqs_body.dict()}")
        except ValidationError as ve:
            logger.error(f"❌ Invalid SQS message format: {ve.json()}")
            return {"status": "Error", "message": "Invalid SQS message format", "details": ve.errors()}

        # ✅ Process Sales Data
        result = sales_processor_service.process_data(validated_sqs_body)

        logger.info(f"✅ Processing result: {result}")

        return {
            "status": "Processed",
            "message": "Sales data successfully processed.",
            "details": result
        }

    except Exception as e:
        logger.exception("❌ Sales Processing Lambda Failed.")
        return {"status": "Error", "message": str(e)}

    finally:
        container.shutdown_resources()  # ✅ Ensures clean resource shutdown