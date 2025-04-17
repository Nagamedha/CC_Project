import json
import boto3
import os
import logging
import requests
from requests_aws4auth import AWS4Auth
from dependency_injector.wiring import inject
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------
# AOSS CONFIGURATION
# ---------------------------------------------
REGION = os.environ.get("AWS_REGION", "us-east-1")
SERVICE = "aoss"
INDEX_NAME = "sales_template_v1"
AOSS_ENDPOINT = "https://vpc-ominights-uh4xluwsmhjtpcziv7uwt472fa.us-east-1.es.amazonaws.com"

HEADERS = {"Content-Type": "application/json"}

credentials = boto3.Session().get_credentials().get_frozen_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    SERVICE,
    session_token=credentials.token
)

# ---------------------------------------------
# Index Template
# ---------------------------------------------
INDEX_TEMPLATE = {
    "settings": {
        "index": {
            "knn": True,
            "number_of_shards": 1,
            "number_of_replicas": 1,
            "knn.algo_param.ef_search": 100,
            "knn.algo_param.ef_construction": 128,
            "knn.algo_param.m": 24
        }
    },
    "mappings": {
        "properties": {
            "record_id": {"type": "keyword"},
            "business_id": {"type": "keyword"},
            "region": {"type": "keyword"},
            "data_type": {"type": "keyword"},
            "department": {"type": "keyword"},
            "timestamp": {"type": "date"},
            "title": {"type": "text", "analyzer": "standard"},
            "description": {"type": "text", "analyzer": "standard"},
            "amount": {"type": "float"},
            "status": {"type": "keyword"},
            "tags": {"type": "keyword"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "faiss"
                }
            }
        }
    }
}

# ---------------------------------------------
# Lambda Handler
# ---------------------------------------------
@inject
def lambda_handler(event, context):
    try:
        logger.info("🚀 Starting AOSS index creation + document insertion")

        # 1. Create index (idempotent — safe if already exists)
        create_index()

        # 2. Index a dummy document
        index_sample_document()

        return {
            "statusCode": 200,
            "body": json.dumps("✅ AOSS index created and document indexed.")
        }

    except Exception as e:
        logger.error(f"❌ Unexpected Error: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps(f"❌ Error: {str(e)}")
        }


# ---------------------------------------------
# Create Index with Template
# ---------------------------------------------
def create_index():
    url = f"{AOSS_ENDPOINT}/{INDEX_NAME}"
    logger.info(f"🔧 Creating index: {INDEX_NAME}")
    response = requests.put(url, headers=HEADERS, auth=awsauth, data=json.dumps(INDEX_TEMPLATE))

    if response.ok:
        logger.info("✅ Index created successfully.")
    elif response.status_code == 400 and "resource_already_exists_exception" in response.text:
        logger.info("ℹ️ Index already exists. Skipping creation.")
    else:
        logger.error(f"❌ Index creation failed: {response.status_code}")
        logger.error(response.text)
        raise Exception("Index creation failed.")


# ---------------------------------------------
# Insert Sample Document
# ---------------------------------------------
def index_sample_document():
    sample_doc = {
        "record_id": "doc-123",
        "business_id": "biz-001",
        "region": "amaravathi",
        "data_type": "sales",
        "department": "retail",
        "timestamp": "2025-03-26T20:00:00Z",
        "title": "High Sales Day",
        "description": "Achieved record sales for product X.",
        "amount": 12000.50,
        "status": "success",
        "tags": ["record", "sales"],
        "embedding": {
            "values": [0.01] * 1536  # Dummy Titan-like vector
        }
    }

    url = f"{AOSS_ENDPOINT}/{INDEX_NAME}/_doc"
    response = requests.post(url, headers=HEADERS, auth=awsauth, data=json.dumps(sample_doc))

    if response.ok:
        logger.info("✅ Document indexed successfully.")
    else:
        logger.error(f"❌ Document index failed: {response.status_code}")
        logger.error(response.text)
        raise Exception("Document indexing failed.")