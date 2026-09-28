import asyncio
import json
import logging
from typing import Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger("WebhookService")

class WebhookService:
    @staticmethod
    async def send_alert_async(
        pit_id: int,
        severity: str,
        road_name: Optional[str],
        latitude: float,
        longitude: float,
        confidence: float,
        webhook_url: Optional[str] = None
    ) -> bool:
        """
        Dispatches an emergency hazard alert payload to configured Webhook (Slack, Discord, or generic endpoint).
        """
        url = webhook_url or settings.ALERT_WEBHOOK_URL
        if not url or not settings.ENABLE_ALERT_WEBHOOKS:
            return False

        payload = {
            "text": f"🚨 [ROAD HAZARD ALERT] Critical Road Defect #{pit_id} detected on {road_name or 'Unassigned Route'}!",
            "pit_id": pit_id,
            "severity": severity,
            "road_name": road_name or "Unknown Road",
            "coordinates": {"latitude": latitude, "longitude": longitude},
            "confidence": f"{confidence * 100:.1f}%",
            "google_maps_url": f"https://www.google.com/maps?q={latitude},{longitude}",
            "timestamp": "now"
        }

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.post(url, json=payload)
                return res.status_code < 400
        except Exception as e:
            logger.warning(f"Webhook delivery failed: {e}")
            return False

    @staticmethod
    def dispatch_alert_background(
        pit_id: int,
        severity: str,
        road_name: Optional[str],
        latitude: float,
        longitude: float,
        confidence: float
    ):
        """Fires and forgets the webhook delivery in the event loop."""
        if settings.ALERT_WEBHOOK_URL:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(
                        WebhookService.send_alert_async(
                            pit_id, severity, road_name, latitude, longitude, confidence
                        )
                    )
            except Exception as e:
                logger.debug(f"Background alert dispatch skipped: {e}")
