from datetime import datetime
from typing import Dict, Any, List

from dependency_injector.wiring import Provide
from shared_layer.aws.adapters.bedrock_adapter import BedrockEmbeddingAdapter
# Import your existing modules
from file_processor.data_formatters.processors.text.spacy_processor import SpacyProcessor
from file_processor.data_formatters.processors.text.txt_preprocessor import TextPreprocessor
from file_processor.model.workers_model import ProcessingContext
from transformers import AutoTokenizer
from shared_layer.aws.adapters.s3_adapter import S3Adapter
from shared_layer.logging.logger import Logger

logger = Logger()  # Logger instance for logging
# -----------------------------
# NEW: Embedding Processor
# -----------------------------

class TXTProcessor:
    """Processes text files efficiently and applies Spacy NLP, Sentiment Analysis & Keyword Extraction."""

    def __init__(
            self,bedrock_repository : BedrockEmbeddingAdapter,spacy_processor: SpacyProcessor,s3_adapter: S3Adapter= Provide['s3_adapter'],
            use_custom_ner: bool = False,
            hf_model_name: str = "bert-base-uncased"
    ):
        """
        Initializes the TXTProcessor.

        Args:
            use_custom_ner (bool): Flag to enable/disable custom NER models.
            hf_model_name (str): Hugging Face model name whose tokenizer we'll use for chunking.
                                 E.g., 'bert-base-uncased' or 'gpt2', etc.
        """
        self.bedrock_repository = bedrock_repository
        self.spacy_processor = spacy_processor
        self.s3_adapter = s3_adapter
        self.use_custom_ner = use_custom_ner
        # Load a tokenizer to approximate Amazon Titan's tokenization approach
        self.tokenizer = AutoTokenizer.from_pretrained(hf_model_name)

    def process(self, context: ProcessingContext) -> Dict[str, Any]:
        """
        Processes a TXT file from S3, applies cleaning, runs Spacy NLP & Sentiment Analysis,
        extracts keywords, and obtains Titan embeddings for each chunk.

        Args:
            context (str): metadata for processing, including bucket name, file key, etc.

        Returns:
            Dict[str, Any]: Processed results with structured data, sentiment, keywords,
                            and Titan embeddings for each chunk.
        """
        try:
            logger.info(
                f"Processing {context.file_key} from {context.bucket_name} with subscription: {context.subscription_type}")

            # 1. Read text from S3
            text_content = self.s3_adapter.get_file_content(context.bucket_name, context.file_key)

            # 2. Clean the text
            cleaned_text = TextPreprocessor.preprocess(text_content)

            # 3. Chunk the text using token-based splitting
            text_batches = self.chunk_text(cleaned_text)
            logger.info(f"Splitting text into {len(text_batches)} chunk(s) for processing...")

            # 4. Apply Spacy NLP Processing (returns list of batches with sentences + metadata)
            spacy_batches = self.spacy_processor.process(
                text_batches=text_batches,
                context=context
            )
            # 5. Add embeddings to each batch
            embedding_spacy_batches = self.bedrock_repository.enrich_with_embeddings(spacy_batches)
            # Add context to each batch
            for batch in embedding_spacy_batches:
                batch["business_region"] = context.business_region
                batch["subscription_type"] = context.subscription_type
                batch["business_id"] = context.business_id
                batch["data_type"] = context.data_type
                batch["file_format"] = context.file_format
                batch["timestamp"] = datetime.now().isoformat() + "Z"

            return embedding_spacy_batches

        except Exception as e:
            logger.error(f"Error processing TXT file {context.file_key}: {str(e)}")
            raise

    def chunk_text(self, text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
        """
        Splits text into chunks based on tokens, preserving a specified token overlap.

        Args:
            text (str): Full cleaned text.
            chunk_size (int): Maximum number of tokens per chunk (default 800).
            overlap (int): Number of tokens to overlap between chunks (default 50).

        Returns:
            List[str]: List of text chunks, each up to `chunk_size` tokens.
        """
        # 1. Convert text into token IDs (without special tokens)
        token_ids = self.tokenizer.encode(text, add_special_tokens=False)

        chunks = []
        idx = 0
        while idx < len(token_ids):
            # 2. Take up to 'chunk_size' tokens
            current_chunk_ids = token_ids[idx: idx + chunk_size]

            # 3. Decode the chunk back into a string
            chunk_str = self.tokenizer.decode(current_chunk_ids, skip_special_tokens=True)
            chunks.append(chunk_str.strip())

            # 4. Move forward by (chunk_size - overlap) tokens
            idx += (chunk_size - overlap)

        return chunks