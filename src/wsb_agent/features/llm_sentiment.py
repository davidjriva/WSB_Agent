"""Local LLM Sentiment Analyzer using Ollama."""

import json
import logging
import re
from typing import Any

import requests
from requests.exceptions import RequestException

from wsb_agent.models import SentimentResult
from wsb_agent.utils.config import FeaturesConfig

logger = logging.getLogger(__name__)

# Fallback values if LLM fails
FALLBACK_SCORE = 0.0
FALLBACK_REASON = "LLM analysis failed. Defaulting to neutral."


class LLMSentimentAnalyzer:
    """Analyzes sentiment of WallStreetBets texts using a local LLM via Ollama."""

    def __init__(self, config: "FeaturesConfig"):
        self.config = config.llm
        self.endpoint = f"{self.config.endpoint.rstrip('/')}/api/generate"
        
        # Verify connection on startup
        self._check_connection()

    def _check_connection(self) -> None:
        """Verify Ollama is reachable."""
        try:
            health_url = self.config.endpoint.rstrip("/") + "/"
            response = requests.get(health_url, timeout=3)
            if response.status_code == 200:
                logger.info(f"Ollama connected successfully at {self.config.endpoint}")
            else:
                logger.warning(f"Ollama returned unexpected status: {response.status_code}")
        except RequestException as e:
            logger.warning(
                f"Could not connect to Ollama at {self.config.endpoint}. "
                f"Is it running? Error: {e}"
            )

    def _build_prompt(self, ticker: str, texts: list[str]) -> str:
        """Construct the system prompt for the financial LLM."""
        combined_text = "\n\n---\n\n".join(texts)
        
        prompt = f"""You are a quantitative financial analyst specializing in retail trading sentiment, specifically the r/WallStreetBets subreddit.
Your task is to analyze the sentiment of the following text discussing the stock ticker ${ticker}.

Understand WSB slang:
- Bullish: "tendies", "moon", "calls", "diamond hands", rocket emojis 🚀
- Bearish: "puts", "guh", "loss porn", "bag holder", "bankruptcy"
- Neutral/Sarcastic: often DD (due diligence) can be neutral until a conclusion is reached.

Read the text and determine the overall sentiment specifically towards the ticker ${ticker}, mapped to a float between -1.0 (extreme bearish/sell) and 1.0 (extreme bullish/buy).

You MUST respond in strict JSON format. Do not include any markdown formatting, conversational text, or explanations outside of the JSON block.

Required JSON Schema:
{{
    "score": <float between -1.0 and 1.0>,
    "reasoning": "<A 1-2 sentence explanation of why this score was given based on the text>"
}}

Text to analyze:
{combined_text}
"""
        return prompt

    def _parse_llm_response(self, raw_text: str) -> dict[str, Any]:
        """Attempt to extract valid JSON from the LLM output."""
        try:
            # First, try to parse it directly
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        # Second, try to extract JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?(.*?)```", raw_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass
                
        # Third, try to find anything resembling a JSON object 
        # (in case the model output trailing text)
        obj_match = re.search(r"\{.*?\}", raw_text, re.DOTALL)
        if obj_match:
            try:
                return json.loads(obj_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.error(f"Failed to extract JSON from LLM output: {raw_text[:200]}...")
        return {"score": FALLBACK_SCORE, "reasoning": "Failed to parse LLM JSON output."}

    def analyze_for_ticker(self, ticker: str, texts: list[str]) -> SentimentResult:
        """Analyze sentiment for a ticker using Ollama."""
        if not texts:
            return SentimentResult(
                ticker=ticker,
                score=0.0,
                label="neutral",
                compound=0.0,
                mention_count=0
            )

        prompt = self._build_prompt(ticker, texts)

        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "format": "json", # Ollama strict JSON mode
            "options": {
                "temperature": 0.1,  # Keep it deterministic
            }
        }

        try:
            response = requests.post(self.endpoint, json=payload, timeout=30)
            response.raise_for_status()
            
            result_data = response.json()
            llm_text = result_data.get("response", "")
            
            parsed = self._parse_llm_response(llm_text)
            
            score = float(parsed.get("score", FALLBACK_SCORE))
            # Clamp between -1.0 and 1.0
            score = max(-1.0, min(1.0, score))
            
            reasoning = parsed.get("reasoning", "No reasoning provided.")
            
            logger.debug(f"LLM Sentiment for {ticker}: {score:.2f} - {reasoning}")
            
            label = "neutral"
            if score > 0.05:
                label = "bullish"
            elif score < -0.05:
                label = "bearish"

            return SentimentResult(
                ticker=ticker,
                score=score,
                label=label,
                compound=score,  # LLM produces a unified compound-like score natively
                mention_count=len(texts),
                metadata={"raw_analysis": llm_text}
            )
            
        except requests.Timeout:
            logger.error(f"Ollama request timed out after 30s for {ticker}")
            return SentimentResult(
                ticker=ticker,
                score=FALLBACK_SCORE,
                label="neutral",
                compound=FALLBACK_SCORE,
                mention_count=len(texts)
            )
        except Exception as e:
            logger.error(f"Ollama generation failed for {ticker}: {e}")
            return SentimentResult(
                ticker=ticker,
                score=FALLBACK_SCORE,
                label="neutral",
                compound=FALLBACK_SCORE,
                mention_count=len(texts)
            )
