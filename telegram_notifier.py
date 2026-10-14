import logging
from typing import Optional

import requests

from config import CRT_BOT_TOKEN, CRT_CHAT_ID

logger = logging.getLogger("CrtTelegram")


def send_telegram_alert(
    message: str,
    parse_mode: Optional[str] = None,
    disable_notification: bool = False,
    *,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> bool:
    """Send a Telegram alert. Plain text is used unless parse_mode is specified."""
    bot_token = token or CRT_BOT_TOKEN
    destination = chat_id or CRT_CHAT_ID

    if not bot_token or not destination:
        logger.error("Telegram bot token or chat ID is missing.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": destination,
        "text": message,
        "disable_notification": disable_notification,
    }

    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.error("Failed to reach Telegram API: %s", exc)
        return False
    except ValueError:
        logger.error("Telegram API returned an invalid JSON response.")
        return False

    if data.get("ok") is True:
        logger.info("Telegram alert sent successfully.")
        return True

    logger.error(
        "Telegram API error: %s",
        data.get("description", "Unknown error"),
    )
    return False


class TelegramNotifier:
    """Compatibility wrapper for code that expects a notifier instance."""

    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> None:
        self.token = token
        self.chat_id = chat_id

    def send_message(self, message: str) -> bool:
        return send_telegram_alert(
            message,
            token=self.token,
            chat_id=self.chat_id,
        )