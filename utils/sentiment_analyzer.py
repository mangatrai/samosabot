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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get thresholds from environment (with defaults)
AUTO_APPROVE_THRESHOLD = float(os.getenv("CONFESSION_AUTO_APPROVE_THRESHOLD", "0.5"))
CONCERNING_THRESHOLD = float(os.getenv("CONFESSION_CONCERNING_THRESHOLD", "-0.6"))

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
            self.analyzer = SentimentIntensityAnalyzer()
            logging.info(f"Sentiment analyzer initialized with thresholds: auto_approve={AUTO_APPROVE_THRESHOLD}, concerning={CONCERNING_THRESHOLD}")
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
            # Get VADER sentiment scores
            scores = self.analyzer.polarity_scores(text)
            compound = scores['compound']
            
            # Classify based on thresholds
            if compound >= AUTO_APPROVE_THRESHOLD:
                category = 'positive'
                auto_approve = True
                confidence = 'high' if compound > 0.7 else 'medium'
            elif compound <= CONCERNING_THRESHOLD:
                category = 'concerning'  # Very negative = concerning content
                auto_approve = False
                confidence = 'high'
            elif compound < -0.1:
                category = 'negative'
                auto_approve = False
                confidence = 'high' if compound < -0.4 else 'medium'
            else:
                category = 'neutral'  # -0.1 to AUTO_APPROVE_THRESHOLD
                auto_approve = False
                confidence = 'low'
            
            return {
                'category': category,
                'score': compound,
                'auto_approve': auto_approve,
                'confidence': confidence,
                'details': scores
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
