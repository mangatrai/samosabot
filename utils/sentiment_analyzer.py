"""
Sentiment Analysis Module for Confessions

Uses VADER (Valence Aware Dictionary and sEntiment Reasoner) for sentiment analysis.
VADER is specifically designed for social media text and works well with informal language.

This module provides sentiment classification for confessions:
- Positive: Auto-approve threshold and above
- Concerning: Very negative sentiment (below concerning threshold)
- Negative: Negative sentiment but not concerning
- Neutral: Neutral sentiment

All sentiment data is stored for analytics and audit purposes.
"""

import os
import logging
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from nltk import sent_tokenize
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get thresholds from environment (with defaults)
AUTO_APPROVE_THRESHOLD = float(os.getenv("CONFESSION_AUTO_APPROVE_THRESHOLD", "0.5"))
CONCERNING_THRESHOLD = float(os.getenv("CONFESSION_CONCERNING_THRESHOLD", "-0.6"))
NEG_SENTENCE_THRESHOLD = float(os.getenv("CONFESSION_NEG_SENTENCE_THRESHOLD", "-0.2"))

# Validate thresholds
if not (-1.0 <= CONCERNING_THRESHOLD < AUTO_APPROVE_THRESHOLD <= 1.0):
    logging.warning(f"Invalid sentiment thresholds: concerning={CONCERNING_THRESHOLD}, auto_approve={AUTO_APPROVE_THRESHOLD}. Using defaults.")
    CONCERNING_THRESHOLD = -0.6
    AUTO_APPROVE_THRESHOLD = 0.5


class ConfessionSentimentAnalyzer:
    """
    Sentiment analyzer for confessions using VADER.
    
    Provides pure sentiment-based classification without keyword lists.
    All sentiment data is stored for analytics and audit purposes.
    """
    
    def __init__(self):
        """Initialize VADER sentiment analyzer."""
        try:
            import nltk
            try:
                nltk.data.find("tokenizers/punkt")
            except LookupError:
                nltk.download("punkt", quiet=True)
            self.analyzer = SentimentIntensityAnalyzer()
            logging.info(
                f"Sentiment analyzer initialized with thresholds: auto_approve={AUTO_APPROVE_THRESHOLD}, "
                f"concerning={CONCERNING_THRESHOLD}, neg_sentence={NEG_SENTENCE_THRESHOLD}"
            )
        except Exception as e:
            logging.error(f"Failed to initialize sentiment analyzer: {e}")
            raise
    
    def analyze(self, text: str) -> dict:
        """
        Analyze confession text using VADER sentiment analysis.
        
        Pure sentiment-based classification - no keyword lists.
        
        Args:
            text: Confession text to analyze
            
        Returns:
            {
                'category': 'positive|negative|neutral|concerning',
                'score': float,  # VADER compound score (-1 to +1)
                'auto_approve': bool,
                'confidence': 'high|medium|low',
                'details': {
                    'pos': float,
                    'neu': float,
                    'neg': float,
                    'compound': float
                }
            }
        """
        try:
            # Sentence-level analysis: split, score each sentence, then aggregate
            sentences = [s.strip() for s in sent_tokenize(text) if s.strip()]
            if not sentences:
                # Fallback: treat whole text as one (e.g. no sentence boundary)
                scores = self.analyzer.polarity_scores(text)
                compound = scores["compound"]
                details = scores
            else:
                compounds = []
                pos_list, neg_list, neu_list = [], [], []
                for sent in sentences:
                    s = self.analyzer.polarity_scores(sent)
                    compounds.append(s["compound"])
                    pos_list.append(s["pos"])
                    neg_list.append(s["neg"])
                    neu_list.append(s["neu"])
                mean_compound = sum(compounds) / len(compounds)
                min_compound = min(compounds)
                # If any sentence is below neg_sentence threshold, use min (one bad sentence pulls down)
                compound = min_compound if min_compound < NEG_SENTENCE_THRESHOLD else mean_compound
                details = {
                    "pos": sum(pos_list) / len(pos_list),
                    "neg": sum(neg_list) / len(neg_list),
                    "neu": sum(neu_list) / len(neu_list),
                    "compound": compound,
                }

            # Classify based on thresholds (unchanged)
            if compound >= AUTO_APPROVE_THRESHOLD:
                category = "positive"
                auto_approve = True
                confidence = "high" if compound > 0.7 else "medium"
            elif compound <= CONCERNING_THRESHOLD:
                category = "concerning"
                auto_approve = False
                confidence = "high"
            elif compound < -0.1:
                category = "negative"
                auto_approve = False
                confidence = "high" if compound < -0.4 else "medium"
            else:
                category = "neutral"
                auto_approve = False
                confidence = "low"

            return {
                "category": category,
                "score": compound,
                "auto_approve": auto_approve,
                "confidence": confidence,
                "details": details,
            }
        except Exception as e:
            logging.error(f"Error analyzing sentiment: {e}")
            # Return neutral on error - queue for review
            return {
                'category': 'neutral',
                'score': 0.0,
                'auto_approve': False,
                'confidence': 'low',
                'details': {'pos': 0.0, 'neu': 1.0, 'neg': 0.0, 'compound': 0.0}
            }
