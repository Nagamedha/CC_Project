import csv
import io
import json
from datetime import datetime
from typing import Optional, Generator, List, Dict, Any
from dependency_injector.wiring import Provide
from file_processor.model.workers_model import ProcessingContext
from shared_layer.aws.adapters.s3_adapter import S3Adapter
from shared_layer.logging.logger import Logger

BATCH_SIZE = 10000  # ✅ Adjustable batch size for processing 1M+ records efficiently
logger = Logger()  # Logger instance for logging

class CSVProcessor:
    def __init__(
            self, s3_adapter: S3Adapter = Provide['s3_adapter']
    ):
        self.s3_adapter = s3_adapter
    """
    Processes large CSV files in batches efficiently.

    This processor:
    - Reads large CSV files in batches (no AI embeddings used).
    - Validates and cleans records.
    - Uses a generator (`yield`) to avoid memory overload.
    """

    def process(self, context: ProcessingContext):
        """
        Process method to conform to the processor interface expected by ProcessorFactory.

        Args:
            bucket_name (str): S3 bucket containing the file.
            file_key (str): S3 object key for the file.
            dep_data_type (str): Department data type (sales, inventory, etc.).
            s3_adapter (S3Adapter): Adapter for S3 operations.
            logger (Logger): Logger instance.

        Returns:
            Generator[List[dict]]: Yields batches of processed records.
        """
        return self.process_csv(context)


    def process_csv(self, context) -> Generator[
        List[Dict[str, Any]], None, None]:
        """
        Reads a CSV file in batches, validates and cleans the data.

        Args:
            bucket_name (str): S3 bucket containing the file.
            file_key (str): S3 object key for the file.
            dep_data_type (str): Department data type (sales, inventory, etc.).
            s3_adapter (S3Adapter): Adapter for S3 operations.
            logger (Logger): Logger instance.

        Returns:
            Generator[List[Dict[str, Any]]]: Yields batches of processed JSON records.
        """
        try:
            logger.info(f"🔄 Starting {context.data_type} {context.subscription_type} batch CSV processing for {context.file_key}...")

            # ✅ Retrieve file from S3 (streaming mode for efficiency)
            file_content = self.s3_adapter.get_object(context.bucket_name, context.file_key)
            if not file_content:
                logger.error(f"❌ Failed to retrieve file: s3://{context.bucket_name}/{context.file_key}")
                raise ValueError(f"File retrieval failed for {context.file_key}")

            logger.info(f"✅ Successfully fetched file: {context.file_key}")

            # ✅ Process CSV in chunks to handle large datasets
            decoded_content = io.StringIO(file_content.decode("utf-8"))
            csv_reader = csv.DictReader(decoded_content)

            # ✅ Ensure headers exist
            if not csv_reader.fieldnames:
                raise ValueError("❌ CSV file has no headers!")

            logger.info(f"✅ Found {len(csv_reader.fieldnames)} columns: {csv_reader.fieldnames}")

            # ✅ Read and process data in batches
            records_batch = []
            total_rows, skipped_rows = 0, 0

            for row in csv_reader:
                total_rows += 1
                cleaned_row = CSVProcessor.validate_and_clean(row, logger)

                if cleaned_row:
                    records_batch.append(cleaned_row)

                if len(records_batch) >= BATCH_SIZE:
                    yield records_batch  # ✅ Yield batch instead of keeping in memory
                    records_batch = []  # ✅ Reset batch

            # ✅ Yield remaining records
            if records_batch:
                yield records_batch

            logger.info(
                f"✅ CSV processing completed: {total_rows} rows read, {total_rows - skipped_rows} valid, {skipped_rows} skipped.")

        except Exception as e:
            logger.exception(f"❌ Error processing CSV file: {str(e)}")
            raise

    @staticmethod
    def validate_and_clean(row: Dict[str, str], logger) -> Optional[Dict[str, Any]]:
        """
        Validates and cleans a single row from the CSV.

        Args:
            row (dict): A dictionary representing a CSV row.
            logger (Logger): Logger instance.

        Returns:
            dict or None: Cleaned record or None if invalid.

        Note:
            Required fields: product_id, customer_id, amount, date.
        """
        try:
            required_fields = ["Product", "Customer ID", "Total Sales", "Quantity", "Payment Method", "Price","Date"]
            missing_fields = [field for field in required_fields if not row.get(field, "").strip()]

            if missing_fields:
                logger.warning(f"⚠️ Skipping row due to missing fields {missing_fields}: {json.dumps(row)}")
                return None

            # ✅ Standardize & clean values
            cleaned_row = {
                "Product": row["Product"].strip(),
                "Customer ID": row["Customer ID"].strip(),
                "Total Sales": CSVProcessor.validate_numeric(row["Total Sales"], logger),
                "Price": CSVProcessor.validate_numeric(row["Price"], logger),
                "Quantity": CSVProcessor.validate_numeric(row["Quantity"], logger),
                "Date": CSVProcessor.standardize_date(row["Date"], logger),
                "Payment Method": row["Payment Method"].strip(),
            }

            return cleaned_row

        except Exception as e:
            logger.exception(f"❌ Unexpected error validating row: {json.dumps(row)} - Error: {str(e)}")
            return None

    @staticmethod
    def validate_numeric(value: str, logger) -> float:
        """
        Validates and converts numeric fields.

        Args:
            value (str): Raw numeric value.
            logger (Logger): Logger instance.

        Returns:
            float: Validated number or 0.0 if invalid.
        """
        try:
            return float(value.strip())
        except ValueError:
            logger.warning(f"⚠️ Invalid numeric value: {value}. Setting to 0.0")
            return 0.0  # Default fallback value

    @staticmethod
    def standardize_date(value: str, logger) -> Optional[str]:
        """
        Standardizes date format to YYYY-MM-DD.

        Args:
            value (str): Raw date value.
            logger (Logger): Logger instance.

        Returns:
            str: Standardized date in YYYY-MM-DD format or None if invalid.

        Note:
            Supports multiple input formats: YYYY-MM-DD, DD-MM-YYYY, MM/DD/YYYY, DD/MM/YYYY.
        """
        date_formats = ["%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y"]

        for fmt in date_formats:
            try:
                return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue

        logger.warning(f"⚠️ Invalid date format: {value}. Setting to NULL.")
        return None  # Return None if date is invalid