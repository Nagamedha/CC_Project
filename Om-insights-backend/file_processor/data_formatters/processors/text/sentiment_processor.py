from textblob import TextBlob
from typing import Dict

class SentimentProcessor:
    """Handles sentiment analysis using TextBlob (can be upgraded to a custom model later)."""

    @staticmethod
    def analyze_sentiment(doc: str) -> Dict[str, float]:
        """
        Analyzes sentiment of a single document using TextBlob.

        Args:
            doc (str): Input text/document.

        Returns:
            Dict[str, float]: Dictionary containing polarity score and sentiment label.
        """
        analysis = TextBlob(str(doc))  # Ensures compatibility
        polarity = analysis.sentiment.polarity  # Range: -1 (negative) to +1 (positive)

        # Classify sentiment based on polarity thresholds
        if polarity > 0.2:
            sentiment = "Positive"
        elif polarity < -0.2:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"

        return {
            "sentiment": sentiment,
            "polarity": polarity
        }

    @staticmethod
    def analyze_batch(doc: str) -> Dict[str, float]:
        """
        Alias to analyze a single text chunk — named 'batch' for consistency with pipeline.

        Args:
            doc (str): Single batch or paragraph of text.

        Returns:
            Dict[str, float]: Sentiment result for the text batch.
        """
        return SentimentProcessor.analyze_sentiment(doc)