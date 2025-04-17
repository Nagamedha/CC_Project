import boto3
from shared_layer.aws.adapters.dynamodb_adapter import DynamoDBAdapter
from shared_layer.logging.logger import Logger


class AWSClientProvider:
    def __init__(self, config):
        self.config = config
        self._aws_region = self.config.get("aws_region", "us-east-1")
        self.logger = Logger()

        # ✅ Use profile directly for now (hardcoded)
        self._session = boto3.Session()

        # Clients
        self._s3_client = None
        self._dynamodb_client = None
        self._aoss_client = None
        self._bedrock_client = None

        # Repositories
        self._dynamo_repository = None

    def _build_client(self, service_name):
        return self._session.client(service_name, region_name=self._aws_region)

    @property
    def s3_client(self):
        if not self._s3_client:
            self._s3_client = self._build_client("s3")
        return self._s3_client

    @property
    def dynamodb_client(self):
        if not self._dynamodb_client:
            self._dynamodb_client = self._build_client("dynamodb")
        return self._dynamodb_client

    @property
    def sqs_client(self):
        return self._build_client("sqs")

    @property
    def ssm_client(self):
        return self._build_client("ssm")

    @property
    def batch_client(self):
        return self._build_client("batch")

    @property
    def aoss_client(self):
        if not self._aoss_client:
            self._aoss_client = self._build_client("opensearch")
        return self._aoss_client

    @property
    def bedrock_client(self):
        if not self._bedrock_client:
            self._bedrock_client = boto3.client("bedrock-runtime", region_name=self._aws_region)
        return self._bedrock_client

    @property
    def dynamo_repository(self):
        if not self._dynamo_repository:
            self._dynamo_repository = DynamoDBAdapter(
                self.dynamodb_client, self.config
            )
        return self._dynamo_repository

    def close(self):
        """Closes AWS Clients (if needed)."""
        self._s3_client = None
        self._dynamodb_client = None
        self._aoss_client = None
        self._dynamo_repository = None
