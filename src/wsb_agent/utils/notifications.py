"""Notifications module for WSB Agent.

Sends alerts (e.g., strong BUY/SELL signals) to external services
like Discord via webhooks.
"""

from __future__ import annotations

import logging
import os
import requests
from typing import Any

from wsb_agent.models import Signal

logger = logging.getLogger("wsb_agent.utils.notifications")


class DiscordNotifier:
    """Sends rich embed messages to a Discord webhook."""

    def __init__(self, webhook_url: str | None = None) -> None:
        """Initialize the notifier.
        
        Args:
            webhook_url: Discord webhook URL. If None, it will look for
                DISCORD_WEBHOOK_URL in environment variables.
        """
        self._webhook_url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL")
        if not self._webhook_url:
            logger.warning("No Discord webhook URL configured. Alerts will be disabled.")

    def is_enabled(self) -> bool:
        """Check if notifications are configured and enabled."""
        return bool(self._webhook_url)

    def send_signals(self, signals: list[Signal]) -> bool:
        """Send alerts for a list of signals.
        
        Only sends signals that represent an actionable trade (BUY/SELL).
        
        Args:
            signals: List of generated signals.
            
        Returns:
            True if successful or disabled, False if request failed.
        """
        if not self.is_enabled() or not signals:
            return True

        actionable = [s for s in signals if s.action in ("BUY", "SELL")]
        if not actionable:
            return True

        logger.info(f"Sending Discord notification for {len(actionable)} signals")
        
        embeds: list[dict[str, Any]] = []
        for signal in actionable[:10]:  # Discord limits to 10 embeds per message
            embeds.append(self._create_embed(signal))

        # Count buys and sells for the header
        buys = sum(1 for s in actionable if s.action == "BUY")
        sells = len(actionable) - buys
        
        header_text = f"🚨 **{len(actionable)} Actionable Signals** ({buys} BUY / {sells} SELL) 🚨"
        
        payload = {
            "username": "WSB Agent Alpha",
            "avatar_url": "https://i.imgur.com/uIOE91s.png", 
            "content": header_text,
            "embeds": embeds,
        }

        try:
            response = requests.post(self._webhook_url, json=payload, timeout=10) # type: ignore
            response.raise_for_status()
            logger.info("Discord notification sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False

    def _create_embed(self, signal: Signal) -> dict[str, Any]:
        """Create a Discord embed dict for a single signal."""
        is_buy = signal.action == "BUY"
        
        # Colors: Green for BUY, Red for SELL
        color = 0x00FF00 if is_buy else 0xFF0000
        
        # Format components
        comps = signal.components
        comp_text = (
            f"**Sentiment:** {comps.get('sentiment', 0):.2f}\n"
            f"**Velocity:** {comps.get('velocity', 0):.2f}\n"
            f"**Volume:** {comps.get('volume', 0):.2f}\n"
            f"**Momentum:** {comps.get('momentum', 0):.2f}"
        )

        return {
            "title": f"[{signal.action}] ${signal.ticker}",
            "description": signal.reasoning,
            "color": color,
            "fields": [
                {
                    "name": "Composite Score",
                    "value": f"{signal.composite_score:.2f} \n*(Confidence: {signal.confidence:.0%})*",
                    "inline": True,
                },
                {
                    "name": "Component Scores (-1 to 1)",
                    "value": comp_text,
                    "inline": True,
                },
            ],
            "footer": {
                "text": f"WSB Agent V1 • {signal.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"
            },
        }
