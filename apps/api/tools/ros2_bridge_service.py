from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="ros2-bridge", version="0.1.0")

ROS2_LEADER_TOPIC = os.getenv("ROS2_LEADER_TOPIC", "/swarm/leader_command")
ROS2_MISSION_CONTROL_TOPIC = os.getenv("ROS2_MISSION_CONTROL_TOPIC", "/swarm/mission_control")


@dataclass
class Ros2Status:
    enabled: bool
    detail: str
    leader_topic: str
    control_topic: str


class Ros2Publisher:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ready = False
        self._detail = "not_initialized"
        self._node = None
        self._leader_pub = None
        self._control_pub = None
        self._string_type = None
        self._init()

    def _init(self) -> None:
        try:
            import rclpy
            from std_msgs.msg import String
        except Exception as exc:  # noqa: BLE001
            self._detail = f"rclpy_unavailable: {exc}"
            return

        try:
            rclpy.init(args=None)
            node = rclpy.create_node("agentic_ros2_bridge")
            leader_pub = node.create_publisher(String, ROS2_LEADER_TOPIC, 10)
            control_pub = node.create_publisher(String, ROS2_MISSION_CONTROL_TOPIC, 10)
            self._node = node
            self._leader_pub = leader_pub
            self._control_pub = control_pub
            self._string_type = String
            self._ready = True
            self._detail = "ready"
        except Exception as exc:  # noqa: BLE001
            self._detail = f"ros2_init_failed: {exc}"

    def publish(self, *, channel: str, payload: dict[str, object]) -> Ros2Status:
        with self._lock:
            if not self._ready:
                return Ros2Status(
                    enabled=False,
                    detail=self._detail,
                    leader_topic=ROS2_LEADER_TOPIC,
                    control_topic=ROS2_MISSION_CONTROL_TOPIC,
                )

            msg = self._string_type()
            msg.data = json.dumps(payload, ensure_ascii=True)
            if channel == "leader":
                self._leader_pub.publish(msg)
            else:
                self._control_pub.publish(msg)

            return Ros2Status(
                enabled=True,
                detail="published",
                leader_topic=ROS2_LEADER_TOPIC,
                control_topic=ROS2_MISSION_CONTROL_TOPIC,
            )

    def health(self) -> Ros2Status:
        return Ros2Status(
            enabled=self._ready,
            detail=self._detail if not self._ready else "ready",
            leader_topic=ROS2_LEADER_TOPIC,
            control_topic=ROS2_MISSION_CONTROL_TOPIC,
        )


_bridge = Ros2Publisher()


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
    status = _bridge.health()
    return asdict(status)


@app.post("/bridge/leader-command")
async def bridge_leader_command(payload: LeaderBridgeRequest) -> dict[str, object]:
    status = _bridge.publish(
        channel="leader",
        payload={
            "kind": "leader_command",
            "mission_id": payload.mission_id,
            "mission_status": payload.mission_status,
            "command": payload.command,
        },
    )
    return {
        "accepted": status.enabled,
        "backend": "ros2",
        "mission_id": payload.mission_id,
        "detail": status.detail,
        "leader_topic": status.leader_topic,
    }


@app.post("/bridge/mission-control")
async def bridge_mission_control(payload: MissionControlBridgeRequest) -> dict[str, object]:
    status = _bridge.publish(
        channel="control",
        payload={
            "kind": "mission_control",
            "action": payload.action,
            "status": payload.status,
            "detail": payload.detail,
        },
    )
    return {
        "accepted": status.enabled,
        "backend": "ros2",
        "action": payload.action,
        "detail": status.detail,
        "control_topic": status.control_topic,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9102)
