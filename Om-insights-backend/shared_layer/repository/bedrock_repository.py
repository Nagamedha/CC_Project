# repositories/bedrock_repository.py
from abc import ABC, abstractmethod
from typing import List


class BedRockRepository(ABC):
    def __init__(self, bedrock_client, config):
        self.bedrock_client = bedrock_client
        self.config = config

    @abstractmethod
    def enrich_with_embeddings(self, spacy_batches: List[dict]) -> List[dict]:
        pass