from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger("agentic-platform")


async def _post_if_configured(url: str, payload: dict[str, Any], timeout_sec: float = 3.0) -> dict[str, Any]:
    if not url:
        return {"enabled": False, "ok": False, "detail": "not_configured"}

    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            body: dict[str, Any] | None = None
            try:
                body = response.json()
            except Exception:  # noqa: BLE001
                body = None
            return {
                "enabled": True,
                "ok": True,
                "status_code": response.status_code,
                "detail": "sent",
                "response": body,
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("bridge_forward_failed", extra={"url": url, "error": str(exc)})
        return {"enabled": True, "ok": False, "detail": str(exc)}


async def dispatch_leader_command(
    settings: Settings,
    *,
    command: str,
    mission_id: str,
    mission_status: str,
) -> dict[str, Any]:
    payload = {
        "command": command,
        "mission_id": mission_id,
        "mission_status": mission_status,
    }
    ros2_result = await _post_if_configured(settings.ros2_bridge_leader_command_url, payload)
    mavsdk_result = await _post_if_configured(settings.mavsdk_bridge_leader_command_url, payload)
    return {"ros2": ros2_result, "mavsdk": mavsdk_result}


async def dispatch_mission_action(
    settings: Settings,
    *,
    action: str,
    status: str,
    detail: str,
) -> dict[str, Any]:
    payload = {
        "action": action,
        "status": status,
        "detail": detail,
    }
    ros2_result = await _post_if_configured(settings.ros2_bridge_mission_control_url, payload)
    mavsdk_result = await _post_if_configured(settings.mavsdk_bridge_mission_control_url, payload)
    return {"ros2": ros2_result, "mavsdk": mavsdk_result}
