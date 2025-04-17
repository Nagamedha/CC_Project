import json
import os
import sys
from unittest.mock import Mock

import pytest

from file_processor.src.processing_lambdas.sales.container import SalesWorkerContainer
from file_processor.src.processing_lambdas.sales.sales_lambda import lambda_handler
from shared_layer.logging.logger import Logger

logger = Logger()  # Logger instance for logging

# ✅ Ensure sys.path includes the project root for module resolution
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if project_root not in sys.path:
    sys.path.append(project_root)


@pytest.fixture(scope="session", autouse=True)
def initialize_container():
    """Fixture to properly initialize and wire the DI container once per test session."""
    container = SalesWorkerContainer()
    container.init_resources()
    container.wire(modules=["file_processor.src.processing_lambdas.sales.sales_lambda"])
    return container


@pytest.fixture
def mock_context():
    context = Mock()
    context.aws_request_id = "test-request-id"
    return context


@pytest.fixture
def mock_s3_event():
    """Fixture to provide the exact event JSON that Sales Lambda receives."""
    return {
        "Records": [
            {
                "messageId": "uuid-1234",
                "receiptHandle": "SomeReceiptHandle",
                "body": json.dumps({'bucket': 'om-insights-file-uploads-dev', 'business_region': 'guntur',
                                    'company': 'grand_venkatesa', 'data_type': 'sales',
                                    'event_time': '2025-03-02T18:49:33.944000+00:00', 'file_format': 'csv',
                                    'file_name': 'smb_sales_data.csv', 'file_size': 30010,
                                    's3_key': 'guntur/pro/grand_venkatesa/sales/smb_sales_data.csv',
                                    'status': 'Received', 'subscription': 'pro'}),
                "attributes": {
                    "ApproximateReceiveCount": "1",
                    "SentTimestamp": "1649997287642",
                    "SenderId": "some-sender-id",
                    "ApproximateFirstReceiveTimestamp": "1649997287645"
                },
                "messageAttributes": {},
                "md5OfBody": "md5checksum",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:region:account-id:queue-name",
                "awsRegion": "us-east-1"
            }
        ]
    }


def test_sales_lambda_handler(mock_s3_event, caplog, mock_context):
    """Test Sales Lambda handler with provided event JSON."""

    logger.info("🚀 Running Sales Lambda Test...")

    # ✅ Invoke the Sales Lambda Handler
    response = lambda_handler(mock_s3_event, mock_context)

    # ✅ Print logs after test execution with formatted timestamps
    logger.info("📌 Captured Logs:")
    # ✅ Print output for debugging
    logger.info(f"📌 Lambda Response:\n{json.dumps(response, indent=2)}")