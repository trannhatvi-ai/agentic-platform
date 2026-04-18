from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="mavsdk-bridge", version="0.1.0")

MAVSDK_SYSTEM_ADDRESS = os.getenv("MAVSDK_SYSTEM_ADDRESS", "udp://:14540")
MAVSDK_TAKEOFF_ALTITUDE_M = float(os.getenv("MAVSDK_TAKEOFF_ALTITUDE_M", "10"))


class MavsdkController:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._system = None
        self._ready = False
        self._detail = "not_initialized"

    async def _ensure_connected(self) -> bool:
        if self._ready and self._system is not None:
            return True
        try:
            from mavsdk import System
        except Exception as exc:  # noqa: BLE001
            self._detail = f"mavsdk_unavailable: {exc}"
            return False

        try:
            system = System()
            await system.connect(system_address=MAVSDK_SYSTEM_ADDRESS)
            async for state in system.core.connection_state():
                if state.is_connected:
                    break
            await system.action.set_takeoff_altitude(MAVSDK_TAKEOFF_ALTITUDE_M)
            self._system = system
            self._ready = True
            self._detail = "connected"
            return True
        except Exception as exc:  # noqa: BLE001
            self._detail = f"mavsdk_connect_failed: {exc}"
            self._ready = False
            self._system = None
            return False

    async def mission_action(self, action: str) -> dict[str, object]:
        async with self._lock:
            ok = await self._ensure_connected()
            if not ok or self._system is None:
                return {"accepted": False, "detail": self._detail}

            try:
                if action in {"start", "resume"}:
                    await self._system.action.arm()
                    await self._system.action.takeoff()
                    return {"accepted": True, "detail": "armed_and_takeoff"}
                if action == "pause":
                    await self._system.action.hold()
                    return {"accepted": True, "detail": "hold"}
                if action == "abort":
                    await self._system.action.return_to_launch()
                    return {"accepted": True, "detail": "rtl"}
                if action == "reset":
                    await self._system.action.disarm()
                    return {"accepted": True, "detail": "disarm"}
                return {"accepted": False, "detail": "unsupported_action"}
            except Exception as exc:  # noqa: BLE001
                return {"accepted": False, "detail": f"mavsdk_action_failed: {exc}"}

    async def health(self) -> dict[str, object]:
        async with self._lock:
            ok = await self._ensure_connected()
            return {"accepted": ok, "detail": self._detail}


_controller = MavsdkController()


class LeaderBridgeRequest(BaseModel):
    command: str
    mission_id: str
    mission_status: str


class MissionControlBridgeRequest(BaseModel):
    action: str
    status: str
    detail: str


@app.get("/bridge/health")
async def health() -> dict[str, object]:
    status = await _controller.health()
    return {
        "accepted": bool(status.get("accepted", False)),
        "backend": "mavsdk",
        "detail": status.get("detail", "unknown"),
        "system_address": MAVSDK_SYSTEM_ADDRESS,
    }


@app.post("/bridge/leader-command")
async def bridge_leader_command(payload: LeaderBridgeRequest) -> dict[str, object]:
    return {
        "accepted": True,
        "backend": "mavsdk",
        "mission_id": payload.mission_id,
        "detail": "command_received",
        "command": payload.command,
    }


@app.post("/bridge/mission-control")
async def bridge_mission_control(payload: MissionControlBridgeRequest) -> dict[str, object]:
    status = await _controller.mission_action(payload.action)
    return {
        "accepted": bool(status.get("accepted", False)),
        "backend": "mavsdk",
        "action": payload.action,
        "detail": status.get("detail", "unknown"),
        "system_address": MAVSDK_SYSTEM_ADDRESS,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9101)
