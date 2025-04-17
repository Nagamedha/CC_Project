import json
from typing import List
from hashlib import sha256

from shared_layer.repository.bedrock_repository import BedRockRepository
from shared_layer.logging.logger import Logger

logger = Logger()

class BedrockEmbeddingAdapter(BedRockRepository):
    def __init__(self, bedrock_client, config, batch_size: int = 10):
        super().__init__(bedrock_client, config)
        self.client = bedrock_client  # Titan client
        self.model_id = "amazon.titan-embed-text-v1"
        self.batch_size = batch_size

    @staticmethod
    def _hash_text(text: str) -> str:
        return sha256(text.encode("utf-8")).hexdigest()

    def embed_batch(self, input_texts: List[str]) -> List[List[float]]:
        """
        Sends one text per Titan request (serially). Titan does not support batch input.

        Args:
            input_texts (List[str]): List of text chunks.

        Returns:
            List[List[float]]: Titan embedding per chunk.
        """
        embeddings = []

        for text in input_texts:
            payload = {
                "inputText": text
            }

            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(payload).encode("utf-8"),
                accept="application/json",
                contentType="application/json"
            )

            body = json.loads(response["body"].read())
            embedding = body.get("embedding")

            if not embedding:
                raise ValueError("Titan response missing 'embedding' key.")

            embeddings.append(embedding)

        return embeddings

    def enrich_with_embeddings(self, spacy_batches: List[dict]) -> List[dict]:
        """
        Appends Titan embeddings to each 512-token SpaCy-processed chunk.

        Args:
            spacy_batches (List[dict]): Sentence-chunked processed text.

        Returns:
            List[dict]: Enriched with `embedding` field per chunk.
        """
        logger.info("🔍 Starting batch embedding enrichment using Amazon Titan...")

        texts_to_embed = []
        batch_refs = []

        for idx, batch in enumerate(spacy_batches):
            text = " ".join(batch.get("sentences", []))
            text_hash = self._hash_text(text)
            batch["text_hash"] = text_hash
            texts_to_embed.append(text)
            batch_refs.append((idx, text_hash))

        for i in range(0, len(texts_to_embed), self.batch_size):
            batch_texts = texts_to_embed[i:i + self.batch_size]
            ref_slice = batch_refs[i:i + self.batch_size]

            embeddings = self.embed_batch(batch_texts)

            if len(embeddings) != len(batch_texts):
                raise RuntimeError(f"❌ Titan returned {len(embeddings)} embeddings for {len(batch_texts)} inputs")

            for (batch_idx, expected_hash), embedding in zip(ref_slice, embeddings):
                original_text = " ".join(spacy_batches[batch_idx]["sentences"])
                actual_hash = self._hash_text(original_text)

                if expected_hash != actual_hash:
                    raise ValueError(f"❌ Hash mismatch on chunk {batch_idx}. Embedding mismatch risk!")

                if not isinstance(embedding, list) or not all(isinstance(x, (float, int)) for x in embedding):
                    raise ValueError(f"❌ Invalid embedding format in batch {batch_idx}")

                spacy_batches[batch_idx]["embedding"] = embedding

        logger.info("✅ All embeddings added successfully.")
        return spacy_batches