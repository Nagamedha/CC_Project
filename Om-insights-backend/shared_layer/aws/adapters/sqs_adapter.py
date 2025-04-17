import json
import boto3
from shared_layer.logging.logger import Logger
from shared_layer.model.response import Response

logger = Logger()


class SQSAdapter:
    def __init__(self, config: dict, sqs_client):
        self.config = config
        self.sqs_client = sqs_client

        # Explicitly get queue URLs from config
        self.worker_queues = {
            queue_name.lower(): queue_info["url"]
            for queue_name, queue_info in config["queues"].items()
        }

    def send_to_worker_queue(self, queue_name, file_metadata):
        queue_url = self.worker_queues.get(queue_name)
        if not queue_url:
            logger.error(f"No queue URL found for {queue_name}. Check routing_config.yaml and environment variables.")
            return Response(
                status="Error",
                message=f"Unknown queue: {queue_name}"
            ).dict()

        try:
            response = self.sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(file_metadata)
            )
            logger.info(f"Message sent to {queue_url}: {response['MessageId']}")
            return Response(
                status="Message sent",
                message=f" queue: {queue_url}"
            ).dict()
        except Exception as e:
            logger.error(f"Failed to send message to {queue_url}. Error: {str(e)}")
            return Response(
                status="Error",
                message=str(e)
            ).dict()
