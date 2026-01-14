"""Webhook client for notifying external audit server of call status changes."""
import httpx
import structlog
from typing import Optional
from .config import get_settings

logger = structlog.get_logger()


class WebhookClient:
    """Client for sending webhook notifications to external audit server."""

    def __init__(self):
        self.settings = get_settings()
        # External audit server base URL (port 8000)
        self.base_url = getattr(self.settings, 'audit_server_url', 'http://localhost:8000')
        self.timeout = 10.0  # 10 seconds timeout

    def notify_call_status(self, call_id: int, status: str) -> bool:
        """
        Notify external audit server about call status change.

        Args:
            call_id: The call ID
            status: The new status (e.g., "Pending", "TranscriptDone", "AuditDone")

        Returns:
            True if webhook was sent successfully, False otherwise
        """
        url = f"{self.base_url}/api/webhook/callStatus"
        payload = {
            "callId": call_id,
            "status": status
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()

                logger.info(
                    "webhook_sent",
                    call_id=call_id,
                    status=status,
                    response_status=response.status_code
                )
                return True

        except httpx.TimeoutException:
            logger.error(
                "webhook_timeout",
                call_id=call_id,
                status=status,
                url=url
            )
            return False

        except httpx.HTTPStatusError as e:
            logger.error(
                "webhook_http_error",
                call_id=call_id,
                status=status,
                status_code=e.response.status_code,
                error=str(e)
            )
            return False

        except Exception as e:
            logger.error(
                "webhook_failed",
                call_id=call_id,
                status=status,
                error=str(e)
            )
            return False

    async def notify_call_status_async(self, call_id: int, status: str) -> bool:
        """
        Async version of notify_call_status.

        Args:
            call_id: The call ID
            status: The new status

        Returns:
            True if webhook was sent successfully, False otherwise
        """
        url = f"{self.base_url}/api/webhook/callStatus"
        payload = {
            "callId": call_id,
            "status": status
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                logger.info(
                    "webhook_sent_async",
                    call_id=call_id,
                    status=status,
                    response_status=response.status_code
                )
                return True

        except httpx.TimeoutException:
            logger.error(
                "webhook_timeout_async",
                call_id=call_id,
                status=status,
                url=url
            )
            return False

        except httpx.HTTPStatusError as e:
            logger.error(
                "webhook_http_error_async",
                call_id=call_id,
                status=status,
                status_code=e.response.status_code,
                error=str(e)
            )
            return False

        except Exception as e:
            logger.error(
                "webhook_failed_async",
                call_id=call_id,
                status=status,
                error=str(e)
            )
            return False


# Singleton instance
_webhook_client: Optional[WebhookClient] = None


def get_webhook_client() -> WebhookClient:
    """Get or create webhook client instance."""
    global _webhook_client
    if _webhook_client is None:
        _webhook_client = WebhookClient()
    return _webhook_client
