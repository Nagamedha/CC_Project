from dependency_injector.wiring import inject
from shared_layer.logging.logger import Logger
from file_processor.src.routing_lambda.container import RoutingContainer
from shared_layer.model.response import Response


# ✅ Use Routing Container
container = RoutingContainer()

# ✅ Use centralized logger
logger = Logger()

@logger.inject_lambda_context(correlation_id_path=Logger.OM_CORRELATION_ID_PATH)
@inject
def lambda_handler(event, context):
    """Main Lambda function to route processing based on file metadata."""
    local_container = RoutingContainer()  # ✅ Initialize container at the start
    local_container.init_resources()  # ✅ Ensure all resources are properly initialized
    try:
        # ✅ Resolve the routing service explicitly
        routing_service = local_container.routing_service()

        # ✅ Call the service directly
        response = routing_service.route_file(event)

        return response

    except Exception as e:
        logger.exception({
            "error_type": "LambdaHandlerError",
            "message": str(e),
            "event": event  # Logs full event for debugging
        })
        return Response(
            status="Error",
            message=str(e),
            context="LambdaHandlerError"
        ).dict()


    finally:
        # ✅ Clean up resources properly
        local_container.shutdown_resources()
        container.shutdown_resources()
# ✅ Wire the container for dependency injection
container.wire(modules=[__name__])