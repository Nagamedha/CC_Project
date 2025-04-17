import time
from shared_layer.logging.logger import Logger

logger = Logger()
class RetryHelper:
    @staticmethod
    def retry(operation, operation_name, max_attempts=2, delay=2):
        attempt = 0
        while attempt < max_attempts:
            try:
                return operation()
            except Exception as e:
                if logger:
                    logger.warning(f"⚠️ Retry {attempt + 1}/{max_attempts} for {operation_name}: {str(e)}")
                time.sleep(delay * (2 ** attempt))  # Exponential backoff
                attempt += 1
        raise Exception(f"❌ Max retries exceeded for {operation_name}")
