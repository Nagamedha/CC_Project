import json
import re

import boto3
from botocore.exceptions import ClientError

from shared_layer.logging.logger import Logger
import chardet

logger = Logger()
class S3Adapter:
    def __init__(self, config: dict):
        self.config = config
        self.s3_client = boto3.client('s3')

    def get_object(self, bucket: str, key: str):
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            logger.info(f"Retrieved object from S3: {bucket}/{key}")
            return response['Body'].read()
        except Exception as e:
            logger.error(f"Error retrieving object from S3: {str(e)}")
            raise

    def put_object(self, bucket: str, key: str, body: bytes):
        try:
            response = self.s3_client.put_object(Bucket=bucket, Key=key, Body=body)
            logger.info(f"Uploaded object to S3: {bucket}/{key}")
            return response
        except Exception as e:
            logger.error(f"Error uploading object to S3: {str(e)}")
            raise

    def delete_object(self, bucket: str, key: str):
        try:
            response = self.s3_client.delete_object(Bucket=bucket, Key=key)
            logger.info(f"Deleted object from S3: {bucket}/{key}")
            return response
        except Exception as e:
            logger.error(f"Error deleting object from S3: {str(e)}")
            raise

    def list_objects(self, bucket: str, prefix: str = ''):
        try:
            response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            logger.info(f"Listed objects in S3: {bucket}/{prefix}")
            return response.get('Contents', [])
        except Exception as e:
            logger.error(f"Error listing objects in S3: {str(e)}")
            raise

    def get_file_content(self, bucket: str, key: str, size_threshold: int = 50 * 1024) -> str:
        """
        Retrieves file content from S3. Automatically decides whether to stream or read fully based on file size.

        Args:
            bucket (str): S3 bucket name
            key (str): S3 object key
            size_threshold (int): Threshold (in bytes) to determine full read vs streaming (default: 50 KB)

        Returns:
            str: File content as a string
        """
        try:
            # Get file metadata (size)
            response = self.s3_client.head_object(Bucket=bucket, Key=key)
            file_size = response["ContentLength"]

            if file_size < size_threshold:
                logger.info(f"File {key} is small ({file_size} bytes), reading fully.")
                return self._read_full_content(bucket, key)
            else:
                logger.info(f"File {key} is large ({file_size} bytes), streaming content.")
                return self._stream_file_content(bucket, key)

        except Exception as e:
            logger.error(f"Error retrieving file {key} from S3: {str(e)}")
            raise

    def _read_full_content(self, bucket: str, key: str, encoding="utf-8") -> str:
        """
        Reads the full content of a small file from S3.

        Args:
            bucket (str): S3 bucket name
            key (str): S3 object key
            encoding (str): Encoding format (default is utf-8)

        Returns:
            str: File content as a string
        """
        try:
            logger.info(f"Fetching small file content from S3: {bucket}/{key}")
            file_data = self.s3_client.get_object(Bucket=bucket, Key=key)['Body'].read()

            # Detect encoding
            detected_encoding = self.detect_encoding(file_data)
            content = file_data.decode(detected_encoding)

            logger.info(f"Successfully decoded small file {key} using {detected_encoding} encoding.")
            return content

        except UnicodeDecodeError as e:
            logger.error(f"Encoding error while decoding file {key}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error retrieving full file content from S3: {str(e)}")
            raise

    def _stream_file_content(self, bucket: str, key: str, chunk_size=4096) -> str:
        """
        Streams a large file from S3 in chunks, avoiding memory overload.

        Args:
            bucket (str): S3 bucket name
            key (str): S3 object key
            chunk_size (int): Size of each chunk (default 4096 bytes)

        Returns:
            str: Processed text content (concatenated from chunks)
        """
        try:
            logger.info(f"Streaming file {key} in chunks of {chunk_size} bytes.")
            obj = self.s3_client.get_object(Bucket=bucket, Key=key)

            content = []
            for chunk in iter(lambda: obj['Body'].read(chunk_size), b""):
                detected_encoding = self.detect_encoding(chunk)
                content.append(chunk.decode(detected_encoding))

            logger.info(f"Successfully streamed large file {key}.")
            return " ".join(content)  # Concatenate chunks into full text

        except Exception as e:
            logger.error(f"Error streaming file {key}: {str(e)}")
            raise

    @staticmethod
    def detect_encoding(file_data: bytes) -> str:
        """
        Detects the encoding of a given file to prevent corruption issues.

        Args:
            file_data (bytes): Raw file content as bytes

        Returns:
            str: Detected encoding format (defaults to utf-8 if detection fails)
        """
        result = chardet.detect(file_data)
        return result["encoding"] if result["encoding"] else "utf-8"

    def is_valid_bucket_name(self, bucket: str) -> bool:
        """
        Validates the S3 bucket name according to AWS naming rules.

        Args:
            bucket (str): S3 bucket name

        Returns:
            bool: True if the bucket name is valid, False otherwise
        """
        if len(bucket) < 3 or len(bucket) > 63:
            return False
        if not re.match(r'^[a-z0-9][a-z0-9.-]+[a-z0-9]$', bucket):
            return False
        if '..' in bucket or '.-' in bucket or '-.' in bucket:
            return False
        return True

    def ensure_bucket_exists(self, bucket: str):
        """
        Ensures that the specified S3 bucket exists. Creates the bucket if it does not exist.

        Args:
            bucket (str): S3 bucket name
        """
        if not self.is_valid_bucket_name(bucket):
            logger.error(f"Invalid bucket name: {bucket}")
            raise ValueError(f"Invalid bucket name: {bucket}")

        try:
            self.s3_client.head_bucket(Bucket=bucket)
            logger.info(f"Bucket {bucket} already exists.")
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                logger.info(f"Bucket {bucket} does not exist. Creating bucket.")
                self.s3_client.create_bucket(Bucket=bucket)
                logger.info(f"Bucket {bucket} created successfully.")
            else:
                logger.error(f"Error checking bucket {bucket}: {str(e)}")
                raise

    def save_json(self, bucket: str, key: str, data: dict):
        """
        Saves a dictionary as a JSON file to the specified S3 bucket and key.

        Args:
            bucket (str): S3 bucket name
            key (str): S3 object key
            data (dict): Data to be saved as JSON
        """
        try:
            self.ensure_bucket_exists(bucket)
            json_data = json.dumps(data)
            self.put_object(bucket, key, json_data.encode('utf-8'))
            logger.info(f"Successfully saved JSON to S3: {bucket}/{key}")
        except Exception as e:
            logger.error(f"Error saving JSON to S3: {str(e)}")
            raise