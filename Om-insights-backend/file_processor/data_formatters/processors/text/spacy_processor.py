import os
import re
import threading
import tarfile
from datetime import datetime

import boto3
import spacy
from typing import List, Dict, Any, Optional, Set
from botocore.exceptions import ClientError
from collections import Counter

from file_processor.data_formatters.processors.text.sentiment_processor import SentimentProcessor
from file_processor.model.workers_model import ProcessingContext
from shared_layer.aws.adapters.s3_adapter import S3Adapter
from shared_layer.logging.logger import Logger
# ✅ Keyword Metadata Extraction
from spacy.lang.en.stop_words import STOP_WORDS as SPACY_STOPWORDS

logger = Logger()  # Logger instance for logging
# ✅ Constants
S3_BUCKET_NAME = "om-insights-model-uploads"
S3_KEY = "spacy_model/en_core_web_sm.tar.gz"
EFS_MODEL_DIR = "/mnt/efs/models/spacy/en_core_web_sm"
TMP_TAR_PATH = "/tmp/en_core_web_sm.tar.gz"
from dependency_injector.wiring import inject, Provide

# ✅ Thread-safe model cache
model_cache = {}
cache_lock = threading.Lock()

s3 = boto3.client("s3")

class SpacyProcessor:
    def __init__(self, s3_adapter: S3Adapter= Provide['s3_adapter']):
        self.s3_adapter = s3_adapter
    @staticmethod
    def ensure_model_downloaded():
        """
        Ensures the spaCy model is in EFS. If missing, downloads from S3 and extracts it.
        """
        if os.path.exists(EFS_MODEL_DIR) and os.path.exists(os.path.join(EFS_MODEL_DIR, "config.cfg")):
            logger.info(f"✅ Model already exists in EFS: {EFS_MODEL_DIR}")
            return True

        logger.warning(f"⚠️ Model missing in EFS: {EFS_MODEL_DIR}. Downloading from S3...")

        try:
            os.makedirs(EFS_MODEL_DIR, exist_ok=True)
        except Exception as e:
            logger.error(f"❌ Error creating EFS directory: {e}")
            return False

        # ✅ Download from S3
        if SpacyProcessor.download_from_s3():
            logger.info(f"✅ Model successfully extracted to EFS: {EFS_MODEL_DIR}")
            return True
        else:
            raise FileNotFoundError(f"❌ Model download failed from S3.")

    @staticmethod
    def download_from_s3():
        """
        Downloads and extracts the SpaCy model from S3 to EFS.
        """
        try:
            logger.info(f"⬇️ Downloading model from s3://{S3_BUCKET_NAME}/{S3_KEY}")
            s3.download_file(S3_BUCKET_NAME, S3_KEY, TMP_TAR_PATH)
            logger.info("✅ Download complete")

            logger.info("📦 Extracting model to EFS...")
            with tarfile.open(TMP_TAR_PATH, "r:gz") as tar:
                tar.extractall(path="/mnt/efs/models/spacy")

            logger.info(f"✅ Model extracted successfully to: {EFS_MODEL_DIR}")

        except ClientError as e:
            logger.error(f"❌ S3 download error: {e}")
            return False
        except tarfile.TarError as e:
            logger.error(f"❌ TAR extraction error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error during model download: {e}")
            return False
        finally:
            if os.path.exists(TMP_TAR_PATH):
                os.remove(TMP_TAR_PATH)
                logger.info("🧹 Cleaned up temporary tar.gz file")

        return True

    @staticmethod
    def get_spacy_model(
            disable_components: Optional[List[str]] = None,
            use_sentencizer: bool = False,
            enable_lemmatizer: bool = True,
            enable_custom_ner: bool = False,
            custom_stopwords: Optional[Set[str]] = None,
            language_code: str = "en"  # placeholder for multi-lingual support
    ):
        """
        Loads the SpaCy model (from EFS in AWS Lambda or locally).

        Args:
            disable_components: List of pipeline components to disable for performance (e.g. ["parser"]).
                               If None, uses the default pipeline in the model.
            use_sentencizer: If True, adds a lightweight 'sentencizer' instead of the full parser
                             to handle sentence splitting.
            enable_lemmatizer: If False, you can remove the built-in lemmatizer for speed. Otherwise keep it.
            enable_custom_ner: If True, adds a rule-based NER pipeline (e.g., BFSI/e-commerce patterns).
            custom_stopwords: A set of domain-specific words to treat as stopwords (in addition to spaCy's default).
            language_code: Placeholder to load different spaCy models (e.g. "xx_ent_wiki_sm" for multi-lingual).
                           Currently uses "en" defaults.

        Returns:
            A loaded spaCy Language object.
        """
        # Use a cache key that depends on disabled components, sentencizer, lemmatizer, custom NER, etc.
        cache_key = f"spacy_model_{disable_components}_{use_sentencizer}_{enable_lemmatizer}_{enable_custom_ner}_{language_code}"

        with cache_lock:
            if cache_key in model_cache:
                return model_cache[cache_key]

            # ✅ Check if running in AWS Lambda
            if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
                logger.info("🟢 Running in AWS Lambda - Using EFS for model storage.")
                SpacyProcessor.ensure_model_downloaded()
                # For advanced multi-lingual, you could decide model_path dynamically (not just EFS_MODEL_DIR)
                model_path = EFS_MODEL_DIR
            else:
                logger.info("🖥️ Running locally - Using installed SpaCy model.")
                # If you want multi-lingual expansions, you could do:
                # model_path = "xx_ent_wiki_sm" if language_code != "en" else "en_core_web_sm"
                model_path = "en_core_web_md"

            logger.info(f"📦 Loading spaCy model from: {model_path}")
            nlp = spacy.load(model_path, disable=disable_components or [])

            # (1) If user wants the 'sentencizer' instead of the parser for sentence splitting
            if use_sentencizer:
                if "parser" in nlp.pipe_names:
                    nlp.remove_pipe("parser")
                if "sentencizer" not in nlp.pipe_names:
                    sentencizer = nlp.create_pipe("sentencizer")
                    nlp.add_pipe(sentencizer, first=True)

            # (2) Optionally remove or confirm the lemmatizer is loaded
            # en_core_web_sm normally includes 'tagger', 'parser', 'ner', 'lemmatizer'
            if not enable_lemmatizer:
                # Remove lemmatizer if present
                if "lemmatizer" in nlp.pipe_names:
                    nlp.remove_pipe("lemmatizer")
            else:
                # Ensure lemmatizer is present if you want it
                if "lemmatizer" not in nlp.pipe_names and "tagger" in nlp.pipe_names:
                    nlp.add_pipe("lemmatizer", after="tagger")

            # (3) If we have domain-specific stopwords, add them
            if custom_stopwords:
                for w in custom_stopwords:
                    nlp.Defaults.stop_words.add(w.lower())

            # (4) Enable a custom rule-based NER if desired
            if enable_custom_ner:
                SpacyProcessor._add_rule_based_ner(nlp)

            # Cache the pipeline
            model_cache[cache_key] = nlp

            return nlp

    @staticmethod
    def _add_rule_based_ner(nlp):
        """
        Adds a basic entity_ruler with BFSI / e-commerce patterns for demonstration.
        You can customize or expand these patterns as needed.
        """
        logger.info("🔧 Adding custom rule-based NER for BFSI & e-commerce patterns.")
        ruler = nlp.add_pipe("entity_ruler", before="ner")
        patterns = [
            # Example BFSI: IFSC code
            {"label": "IFSC", "pattern": [{"REGEX": r"^[A-Z]{4}0[A-Z0-9]{6}$"}]},
            # Example e-com or BFSI: Transaction ID
            {"label": "TRANSACTION_ID", "pattern": [{"TEXT": {"REGEX": r"TXN\d{6,}"}}]},
            # Add more domain patterns here
        ]
        ruler.add_patterns(patterns)


    def process(self,
            text_batches: List[str],
            context:ProcessingContext,
            batch_size: int = 10,
            n_process: int = 1,
            disable_components: Optional[List[str]] = None,
            use_sentencizer: bool = False,
            enable_lemmatizer: bool = True,
            enable_custom_ner: bool = False,
            custom_stopwords: Optional[Set[str]] = None,
            advanced_ner_merge: bool = True,
            language_code: str = "en"
    ):
        """
        Processes text batches with SpaCy (NER, POS, Sentence Segmentation).
        Returns a list of per-batch outputs for OpenSearch indexing.

        Args:
            text_batches: List of text chunks (~1MB each).
            batch_size: Size of sub-batches spaCy processes in parallel.
            n_process: Number of processes to use (1 for Lambda).
            disable_components, use_sentencizer, etc.: spaCy config options.
            business_id: Used for saving global noise word profiles.

        Returns:
            List of per-batch dicts: {
                batch_id, sentences, indexed_metadata
            }
        """
        # Load the model with optional features
        nlp = SpacyProcessor.get_spacy_model(
            disable_components=disable_components,
            use_sentencizer=use_sentencizer,
            enable_lemmatizer=enable_lemmatizer,
            enable_custom_ner=enable_custom_ner,
            custom_stopwords=custom_stopwords,
            language_code=language_code
        )

        batch_results = []
        token_freq_global = Counter()
        named_entities_global = set()
        batch_id = 0

        for doc in nlp.pipe(text_batches, batch_size=batch_size, n_process=n_process):
            batch_id += 1
            sentences = SpacyProcessor.extract_sentences(doc)
            named_ents = SpacyProcessor.extract_named_entities(doc)
            pos_tags = SpacyProcessor.extract_pos_tags(doc)
            sentiment_analysis = SentimentProcessor.analyze_batch(doc)
            # Track global noise profile
            named_entities_global.update(
                re.sub(r"[^\w\s]", "", ent["text"].lower()) for ent in named_ents
            )
            token_freq_global.update(
                token.text.lower() for token in doc if not token.is_punct and len(token.text) > 2
            )

            indexed_metadata = SpacyProcessor._extract_batch_metadata(
                pos_tags=pos_tags,
                named_entities=named_ents,
                global_named_entities=named_entities_global
            )

            batch_results.append({
                "batch_id": batch_id,
                "sentences": sentences,
                "indexed_metadata": indexed_metadata,
                "sentiment_analysis":sentiment_analysis
            })

        # 🔁 Save global noise profile once (for use in embedding or filtering downstream)
        if context.business_id:
            auto_noise_words = {
                word for word, _ in token_freq_global.most_common(50)
                if word not in named_entities_global
            }
            payload = {
                "business_id": context.business_id,
                "last_updated": datetime.now().isoformat(),
                "noise_words": sorted(auto_noise_words)
            }
            self.s3_adapter.save_json(
                bucket="noiseprofiles",
                key=f"{context.business_id}/noise_words.json",
                data=payload
            )
        return batch_results

    @staticmethod
    def extract_sentences(doc) -> List[str]:
        """
        Extracts sentences from the document with proper segmentation
        (parser-based or sentencizer-based, depending on pipeline).
        """
        return [sent.text.strip() for sent in doc.sents if len(sent.text.strip()) > 1]

    @staticmethod
    def extract_named_entities(doc) -> List[Dict[str, str]]:
        """
        Extracts Named Entities and their types.

        Returns:
            List of {"text": entity_text, "label": entity_type}
        """
        return [{"text": ent.text, "label": ent.label_} for ent in doc.ents]

    @staticmethod
    def extract_pos_tags(doc) -> List[Dict[str, str]]:
        """
        Extracts Part-of-Speech (POS) tags for words.

        Returns:
            List of {"word": token.text, "pos": token.pos_}
        """
        # We skip punctuation for clarity
        return [{"word": token.text, "pos": token.pos_} for token in doc if not token.is_punct]

    @classmethod
    @inject
    def _extract_indexed_metadata_from_stats(
            cls,
            spacy_text_data: List[Dict[str, Any]],
            token_freq: Counter,
            named_entities: Set[str],
            business_id: str = None,
            max_noise_words: int = 50,
            save_to_s3: bool = True,
            s3_adapter: S3Adapter = Provide['s3_adapter']
    ) -> Dict[str, Any]:
        # Top-N frequent tokens not in named entities → noise
        auto_noise = {
            word for word, _ in token_freq.most_common(max_noise_words)
            if word not in named_entities
        }

        if save_to_s3 and business_id:
            payload = {
                "business_id": business_id,
                "last_updated": datetime.utcnow().isoformat(),
                "noise_words": sorted(auto_noise)
            }
            #TODO: Instead of S3 we will use DynamoDB
            s3_adapter.save_json(f"noise_profiles/{business_id}/noise_words.json", payload)

        BASE_NOISE = SPACY_STOPWORDS.union(auto_noise)

        def is_noise(token: str) -> bool:
            t = token
            return (
                    t in BASE_NOISE or
                    len(t) < 3 or
                    re.search(r"(.)\1{2,}", t) or
                    re.fullmatch(r"\d+", t)
            )

        useful_ner_labels = {
            "ORG": ("entities", 0.9),
            "PERSON": ("entities", 0.9),
            "PRODUCT": ("entities", 0.9),
            "GPE": ("locations", 0.85),
            "DATE": ("dates", 0.8),
            "CARDINAL": ("numbers", 0.6),
            "MONEY": ("numbers", 0.7)
        }

        useful_pos_tags = {
            "NOUN": ("keywords", 0.6),
            "PROPN": ("keywords", 0.7),
            "NUM": ("numbers", 0.5)
        }

        merged = {
            "entities": set(),
            "locations": set(),
            "dates": set(),
            "numbers": set(),
            "keywords": set()
        }
        ranked_keywords = []
        all_keywords = set()
        seen_lower = set()

        for ent in named_entities:
            if not ent or is_noise(ent):
                continue
            seen_lower.add(ent)
            merged["entities"].add(ent)
            ranked_keywords.append({"keyword": ent, "score": 0.9})
            all_keywords.add(ent)

        for token in spacy_text_data[0].get("pos_tags", []):
            pos = token.get("pos", "").upper()
            word = token.get("word", "").strip()
            if not word or pos not in useful_pos_tags:
                continue
            normalized = re.sub(r"[^\w\s]", "", word).lower()
            if normalized in seen_lower or is_noise(normalized):
                continue
            seen_lower.add(normalized)
            group, score = useful_pos_tags[pos]
            merged[group].add(word)
            ranked_keywords.append({"keyword": word, "score": score})
            all_keywords.add(word)

        return {
            "entities": sorted(merged["entities"]),
            "locations": sorted(merged["locations"]),
            "dates": sorted(merged["dates"]),
            "numbers": sorted(merged["numbers"]),
            "keywords": sorted(merged["keywords"]),
            "all": sorted(all_keywords),
            "ranked_keywords": sorted(ranked_keywords, key=lambda x: -x["score"])
        }

    @staticmethod
    def _extract_batch_metadata(
            pos_tags: List[Dict[str, str]],
            named_entities: List[Dict[str, str]],
            global_named_entities: Set[str],
            max_noise_words: int = 50
    ) -> Dict[str, Any]:
        """
        Extracts indexed metadata for a single batch.
        """
        BASE_NOISE = SPACY_STOPWORDS

        def is_noise(token: str) -> bool:
            t = token.lower()
            return (
                t in BASE_NOISE or
                len(t) < 3 or
                re.search(r"(.)\1{2,}", t) or
                re.fullmatch(r"\d+", t)
            )

        useful_ner_labels = {
            "ORG": ("entities", 0.9),
            "PERSON": ("entities", 0.9),
            "PRODUCT": ("entities", 0.9),
            "GPE": ("locations", 0.85),
            "DATE": ("dates", 0.8),
            "CARDINAL": ("numbers", 0.6),
            "MONEY": ("numbers", 0.7)
        }

        useful_pos_tags = {
            "NOUN": ("keywords", 0.6),
            "PROPN": ("keywords", 0.7),
            "NUM": ("numbers", 0.5)
        }

        merged = {
            "entities": set(),
            "locations": set(),
            "dates": set(),
            "numbers": set(),
            "keywords": set()
        }
        ranked_keywords = []
        all_keywords = set()
        seen = set()

        # NER
        for ent in named_entities:
            text = ent.get("text", "").strip()
            label = ent.get("label", "")
            norm = re.sub(r"[^\w\s]", "", text).lower()
            if not text or is_noise(norm) or norm in seen:
                continue
            group, score = useful_ner_labels.get(label, ("entities", 0.5))
            merged[group].add(text)
            ranked_keywords.append({"keyword": text, "score": score})
            all_keywords.add(text)
            seen.add(norm)

        # POS
        for token in pos_tags:
            word = token.get("word", "").strip()
            pos = token.get("pos", "").upper()
            norm = re.sub(r"[^\w\s]", "", word).lower()
            if not word or pos not in useful_pos_tags or norm in seen or is_noise(norm):
                continue
            group, score = useful_pos_tags[pos]
            merged[group].add(word)
            ranked_keywords.append({"keyword": word, "score": score})
            all_keywords.add(word)
            seen.add(norm)

        return {
            "entities": sorted(merged["entities"]),
            "locations": sorted(merged["locations"]),
            "dates": sorted(merged["dates"]),
            "numbers": sorted(merged["numbers"]),
            "keywords": sorted(merged["keywords"]),
            "all": sorted(all_keywords),
            "ranked_keywords": sorted(ranked_keywords, key=lambda x: -x["score"])
        }

# ✅ Preload models in AWS Lambda environment to reduce cold start time (optional)
if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    try:
        # Example: preload with the default pipeline (parser-based)
        SpacyProcessor.get_spacy_model()
        logger.info("✅ Preloaded spaCy model in Lambda environment.")
    except Exception as e:
        logger.error(f"❌ Failed to preload spaCy model: {e}")