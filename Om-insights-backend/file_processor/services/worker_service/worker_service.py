# file_processor/services/worker_service/sales/sales_processor.py

from abc import ABC, abstractmethod
from typing import Dict


class WorkerService(ABC):
    """
    Abstract base class for processing sales data.
    """

    @abstractmethod
    def process_data(self, event: dict) -> Dict:
        """
        Processes sales data from parsed file event.
        Args:
            event (dict): File metadata and pointer.
        Returns:
            Dict: Processing result.
        """
        pass
