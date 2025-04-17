from abc import ABC, abstractmethod


#TODO: Same thign here bring it to shread_layer and make these classes absolutly generic enough to be used in other parts of the project
class AOSSRepository(ABC):
    def __init__(self, aoss_client, config):
        """Initialize the repository with a AOSS client."""
        self.aoss_client = aoss_client
        self.config = config

    @abstractmethod
    def index_unstructured_data(self, parsed_data):
        pass

    @abstractmethod
    def describe_collections(self):
        pass

    @abstractmethod
    def search(self, collection_id, query):
        pass