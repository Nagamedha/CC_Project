import os
import tarfile
import boto3
import spacy
from botocore.exceptions import ClientError
from utils.logging import logger

# 🔧 CONFIG
S3_BUCKET = "om-insights-model-uploads"
S3_KEY = "spacy_model/en_core_web_sm.tar.gz"
EFS_MODEL_DIR = "/mnt/efs/models/spacy/en_core_web_sm"
TMP_TAR_PATH = "/tmp/en_core_web_sm.tar.gz"

s3 = boto3.client("s3")

def lambda_handler(event, context):
    try:
        # Step 1: Check if model already exists in EFS
        if os.path.exists(EFS_MODEL_DIR) and os.path.exists(os.path.join(EFS_MODEL_DIR, "config.cfg")):
            logger.info(f"✅ Model already exists at {EFS_MODEL_DIR}")
        else:
            # Step 2: Download model from S3 to /tmp
            logger.info(f"⬇️ Downloading model from s3://{S3_BUCKET}/{S3_KEY}")
            s3.download_file(S3_BUCKET, S3_KEY, TMP_TAR_PATH)
            logger.info("✅ Download complete")

            # Step 3: Extract into EFS
            logger.info("📦 Extracting model to EFS...")
            with tarfile.open(TMP_TAR_PATH, "r:gz") as tar:
                tar.extractall(path="/mnt/efs/models/spacy")

            logger.info(f"✅ Model extracted to: {EFS_MODEL_DIR}")

        # Step 4: Verify Extraction - List Files
        extracted_files = []
        for root, dirs, files in os.walk(EFS_MODEL_DIR):
            for name in files:
                extracted_files.append(os.path.relpath(os.path.join(root, name), EFS_MODEL_DIR))

        logger.info(f"📂 Extracted Files in {EFS_MODEL_DIR}:")
        for item in extracted_files[:10]:  # Print first 10 files
            logger.info(f" - {item}")

        # Step 5: Load the model
        logger.info(f"📦 Loading model from: {EFS_MODEL_DIR}")
        nlp = spacy.load(EFS_MODEL_DIR)

        # Step 6: Run a test NLP task
        test_text = "Apple is looking at buying a U.K. startup for $1 billion."
        doc = nlp(test_text)
        entities = [(ent.text, ent.label_) for ent in doc.ents]

        logger.info(f"🔍 Test Text: {test_text}")
        logger.info(f"🔍 Extracted Entities: {entities}")

        return {
            "statusCode": 200,
            "body": {
                "message": "Model successfully downloaded, extracted, and tested.",
                "entities": entities,
                "extracted_files": extracted_files[:5]  # Show first 5 files for verification
            }
        }

    except ClientError as e:
        logger.error(f"❌ S3 Download Error: {e}")
        return {
            "statusCode": 500,
            "body": f"S3 error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": f"Error: {str(e)}"
        }