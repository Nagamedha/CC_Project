import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import os
import boto3
import requests
from datetime import datetime
from shared_layer.repository.aoss_repository import AOSSRepository
from shared_layer.logging.logger import Logger
from requests_aws4auth import AWS4Auth
from file_processor.search.index_manager import IndexTemplateManager

logger = Logger()

REGION = os.environ.get("AWS_REGION", "us-east-1")
SERVICE = "es" # For Amazon OpenSearch-managed domains, keep this as "es".

# AWS SigV4 Auth setup
credentials = boto3.Session().get_credentials().get_frozen_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    SERVICE,
    session_token=credentials.token
)

HEADERS = {"Content-Type": "application/json"}


class AOSSAdapter(AOSSRepository):
    def __init__(self, aoss_client, config: dict):
        super().__init__(aoss_client, config)
        self.endpoint = config.get("aoss", {}).get("endpoint")
        self.index_name = config.get("aoss", {}).get("index_name")

        if not self.endpoint or not self.index_name:
            raise ValueError("AOSSAdapter config must include 'endpoint' and 'index_name'.")

    def index_unstructured_data(self, parsed_data: dict):
        logger.info("🚀 Starting to index unstructured data")

        index_template = self._load_index_template()
        self._create_index_if_not_exists(index_template)

        # 2. Prepare bulk request payload
        bulk_payload = ""
        timestamp = datetime.now().isoformat() + "Z"

        for batch in parsed_data:
            batch["timestamp"] = timestamp
            # Bulk format: action metadata + document
            action = {"index": {"_index": self.index_name}}
            bulk_payload += f"{json.dumps(action)}\n{json.dumps(batch)}\n"

        # 3. Send bulk request
        url = f"{self.endpoint}/_bulk"
        logger.info(f"📤 Sending bulk request to OpenSearch index: {self.index_name}")

        try:
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                auth=awsauth,
                data=bulk_payload,
                verify=False  # ⚠️ Disable only in dev
            )
            result = response.json()

            if response.status_code != 200 or result.get("errors"):
                failed_items = [
                    item for item in result.get("items", [])
                    if "error" in item.get("index", {})
                ]
                logger.warning(f"❌ {len(failed_items)} batch(es) failed during indexing.")

                for item in failed_items:
                    err = item["index"]["error"]
                    logger.error(f"🔴 Failed batch: {err.get('reason', 'Unknown error')}")

                raise Exception("One or more batches failed during bulk indexing.")

            logger.info("✅ All batches indexed successfully.")

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Bulk request failed: {e}")
            raise
    @staticmethod
    def _load_index_template(self) -> dict:
        try:
            template = IndexTemplateManager.get_template(self.index_name)
            logger.info(f"✅ Loaded index template for '{self.index_name}'")
            return template
        except Exception as e:
            logger.error(f"❌ Failed to load index template: {e}")
            raise

    @staticmethod
    def _create_index_if_not_exists(self, template: dict):
        url = f"{self.endpoint}/{self.index_name}"
        logger.info(f"🔍 Checking if index '{self.index_name}' exists or needs creation")

        try:
            response = requests.put(
                url, headers=HEADERS, auth=awsauth, data=json.dumps(template),verify=False
            )

            if response.ok:
                logger.info("✅ Index created successfully.")
            elif response.status_code == 400 and "resource_already_exists_exception" in response.text:
                logger.info("ℹ️ Index already exists. Skipping creation.")
            else:
                logger.error(f"❌ Index creation failed ({response.status_code}): {response.text}")
                raise Exception("Index creation failed.")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Index creation error: {e}")
            raise
    @staticmethod
    def _validate_document(self, document: dict) -> dict:
        # Optional future: Add schema validation (e.g., Pydantic or JSON schema)
        if "embedding" in document and len(document["embedding"]) != 1536:
            raise ValueError("Invalid embedding dimension. Expected 1536.")
        return document
    @staticmethod
    def _index_document(self, document: dict):
        url = f"{self.endpoint}/{self.index_name}/_doc"
        logger.info(f"📥 Indexing document to '{self.index_name}'")

        try:
            response = requests.post(
                url, headers=HEADERS, auth=awsauth, data=json.dumps(document),verify=False
            )
            if response.ok:
                logger.info("✅ Document indexed successfully.")
            else:
                logger.error(f"❌ Document index failed ({response.status_code}): {response.text}")
                raise Exception("Document indexing failed.")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error during document indexing: {e}")
            raise

    def describe_collections(self):
        logger.info("📚 Describing AOSS collections")
        return self.aoss_client.list_collections()

    def search(self, collection_id: str, query: dict):
        logger.info(f"🔍 Searching collection '{collection_id}' with query: {query}")
        # Future implementation placeholder
        pass

