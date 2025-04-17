import json
import os
import sys
from dependency_injector.wiring import Provide, inject
from file_processor.src.routing_lambda.container import RoutingContainer as Container
from file_processor.src.routing_lambda.main_router_lambda import lambda_handler
from shared_layer.logging.logger import Logger

# ✅ Ensure sys.path includes the project root for module resolution
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if project_root not in sys.path:
    sys.path.append(project_root)

# ✅ Use centralized logger
logger = Logger()


def main():
    """
    Run the routing_lambda handler locally with a simulated S3 event.
    """
    logger.info("🚀 Starting local execution of routing_lambda...")

    # ✅ Set up container for dependency injection
    container = Container()
    container.wire(modules=["file_processor.src.routing_lambda.main_router_lambda"])

    # ✅ Manually resolve dependencies
    routing_service = container.routing_service()

    # ✅ Mock S3 event as it would come from SQS
    mock_event = {
        "Records": [
            {
                "body": json.dumps({
                    "Records": [
                        {
                            "eventVersion": "2.1",
                            "eventSource": "aws:s3",
                            "awsRegion": "us-east-1",
                            "eventTime": "2025-03-02T18:49:33.944Z",
                            "eventName": "ObjectCreated:Put",
                            "userIdentity": {"principalId": "AWS:AIDAW5WU5E6SIAQ4CVSAW"},
                            "requestParameters": {"sourceIPAddress": "108.210.178.97"},
                            "responseElements": {
                                "x-amz-request-id": "2C58GY7HP054BWW4",
                                "x-amz-id-2": "dpBeDesBzpCN50ZiEa+mSd6fM0At65VLQamZdawEDrXh8USZzeo5ySX+9rR99PnnLz4nQQTmIRsFTDgVJ/Ivs68NzYsd4CUy"
                            },
                            "s3": {
                                "s3SchemaVersion": "1.0",
                                "configurationId": "MWNjMzA5MDktOTY3Yy00NzRmLWFlZDUtNjBjZmUyMGUwYjUw",
                                "bucket": {
                                    "name": "om-insights-file-uploads-dev",
                                    "ownerIdentity": {"principalId": "A14JTUOTL4UJNF"},
                                    "arn": "arn:aws:s3:::Om-insights-file-uploads-dev"
                                },
                                "object": {
                                    "key": "guntur/pro/grand_venkatesa/sales/business_news_test.txt",
                                    "size": 30010,
                                    "eTag": "a1fce9707868e894598c52a343113f4e",
                                    "versionId": "hL8tAa7MbYL3IKhQnTS3TP0K.M5lvqw.",
                                    "sequencer": "0067C4A83DE579EF61"
                                }
                            }
                        }
                    ]
                })
            }
        ]
    }

    # ✅ Mock AWS Lambda Context
    class MockContext:
        function_name = "local-test"
        memory_limit_in_mb = 128
        invoked_function_arn = "arn:aws:routing_lambda:local:123456789012:function:local-test"
        aws_request_id = "local-request-id"

    mock_context = MockContext()

    # ✅ Call lambda_handler with manually injected dependencies
    logger.info("📡 Calling lambda_handler with mock event...")

    @inject
    def wrapped_lambda_handler(event, context, routing_service: Provide[Container.routing_service]):
        return lambda_handler(event, context)

    result = wrapped_lambda_handler(mock_event, mock_context, routing_service=routing_service)

    # ✅ Print the result
    logger.info(f"📌 Lambda handler result:\n{json.dumps(result, indent=2)}")


if __name__ == "__main__":
    main()