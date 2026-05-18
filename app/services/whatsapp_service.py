"""WhatsApp service.

Phase 0/1-4 stub: in dev mode, would-be sends are logged to the console.
Phase 5 wires the real Meta WhatsApp Cloud API. Phase 3 builds the call
sites that use this module.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


def send_template(
    *,
    template_name: str,
    to_group_id: str | None = None,
    variables: dict[str, Any] | None = None,
) -> None:
    """Send a pre-approved WhatsApp template message.

    Dev: log only. Prod: call Meta Cloud API (wired in Phase 5).
    """
    settings = get_settings()
    payload = {
        "template": template_name,
        "to": to_group_id or settings.whatsapp_group_id,
        "variables": variables or {},
    }

    if settings.is_dev:
        print(f"[whatsapp:dev] would send: {payload}", flush=True)
        log.info("whatsapp_sent_dev", **payload)
        return

    raise RuntimeError(
        "Real WhatsApp delivery is not configured. "
        "Phase 5 wires the Meta Cloud API; see implementation_plan.md."
    )
