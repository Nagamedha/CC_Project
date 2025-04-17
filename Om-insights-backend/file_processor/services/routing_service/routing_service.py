# file_processor/services/routing_service/routing_service.py
from abc import ABC, abstractmethod
from typing import Dict


class RoutingService(ABC):
    """
    Abstract base class defining the routing service contract.
    """

    @abstractmethod
    def route_file(self, event: dict) -> Dict:
        """
        Process and route the file based on the given event.
        """
        pass
