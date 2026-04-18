from __future__ import annotations

import math
import re
import threading
import time
from dataclasses import asdict, dataclass
from typing import Literal

from app.config import get_settings


PhaseStatus = Literal["pending", "active", "completed"]


@dataclass(frozen=True)
class Phase:
    id: int
    name: str
    detail: str
    status: PhaseStatus


@dataclass(frozen=True)
class Telemetry:
    battery_pct: int
    altitude_m: float
    speed_ms: float
    confidence: float


@dataclass(frozen=True)
class MissionState:
    title: str
    progress_label: str
    phases: list[Phase]
    telemetry: Telemetry
    mission_state: str
    time_remaining_sec: int
    reasoning_trace: list[str]
    checklist: list[dict[str, object]]
    swarm_context: dict[str, object]
    follower_status: dict[str, object]
    esim_vision: dict[str, object]
    map_2d: dict[str, object]
    vlm_profile: dict[str, object]
    follower_thoughts: list[str]


PHASE_TEMPLATE = [
    (1, "PHASE 1", "Acquire leader command"),
    (2, "PHASE 2", "Align formation slot"),
    (3, "PHASE 3", "Track corridor and obstacles"),
    (4, "PHASE 4", "Micro-replan and hold spacing"),
    (5, "PHASE 5", "Execute waypoint objective"),
    (6, "PHASE 6", "Report completion and await next"),
]


_DEFAULT_LEADER_COMMAND = "Leader: Form wedge-left, hold 12m altitude, follow waypoint A3."
TOTAL_MISSION_SECONDS = 150
PHASE_SECONDS = TOTAL_MISSION_SECONDS / len(PHASE_TEMPLATE)

MissionStatus = Literal["idle", "ready", "running", "paused", "aborted", "completed"]


@dataclass
class MissionRuntime:
    mission_id: str
    leader_command: str
    assigned_at: int
    status: MissionStatus
    progress_sec: float
    last_tick: float
    objective: str
    target_waypoint: str
    target_altitude_m: float


_runtime_lock = threading.Lock()
_runtime = MissionRuntime(
    mission_id="mission-idle",
    leader_command=_DEFAULT_LEADER_COMMAND,
    assigned_at=int(time.time()),
    status="idle",
    progress_sec=0.0,
    last_tick=time.time(),
    objective="Awaiting leader mission assignment",
    target_waypoint="A3",
    target_altitude_m=12.0,
)

SIM_ONLINE_TIMEOUT_SEC = 3.0
MAP_TRAIL_LIMIT = 120

_sim_lock = threading.Lock()
_sim_state: dict[str, object] = {
    "updated_at": 0.0,
    "telemetry": None,
    "vision": None,
    "uav_position": {"x": 44.0, "y": 45.0},
    "waypoint_position": {"x": 63.0, "y": 32.0},
    "obstacles": [
        {"x": 28.0, "y": 41.0},
        {"x": 62.0, "y": 28.0},
        {"x": 74.0, "y": 57.0},
    ],
    "trail": [{"x": 20.0, "y": 66.0}, {"x": 30.0, "y": 58.0}, {"x": 44.0, "y": 45.0}],
}


def ingest_sim_telemetry(payload: dict[str, float]) -> int:
    with _sim_lock:
        now = time.time()
        _sim_state["updated_at"] = now
        _sim_state["telemetry"] = {
            "battery_pct": int(round(payload["battery_pct"])),
            "altitude_m": round(payload["altitude_m"], 1),
            "speed_ms": round(payload["speed_ms"], 1),
            "confidence": round(payload["confidence"], 2),
        }
        return int(now)


def ingest_sim_vision(payload: dict[str, object]) -> int:
    with _sim_lock:
        now = time.time()
        _sim_state["updated_at"] = now
        _sim_state["vision"] = {
            "scene_summary": payload["scene_summary"],
            "risk_level": payload["risk_level"],
            "frame_url": payload.get("frame_url"),
            "stream_url": payload.get("stream_url"),
            "detected_objects": payload.get("detected_objects", []),
        }
        return int(now)


def ingest_sim_map_point(payload: dict[str, object]) -> int:
    with _sim_lock:
        now = time.time()
        _sim_state["updated_at"] = now
        point = {"x": float(payload["x"]), "y": float(payload["y"])}
        tag = str(payload["tag"])
        if tag == "uav":
            _sim_state["uav_position"] = point
            trail = list(_sim_state.get("trail", []))
            trail.append(point)
            _sim_state["trail"] = trail[-MAP_TRAIL_LIMIT:]
        elif tag == "waypoint":
            _sim_state["waypoint_position"] = point
        elif tag == "obstacle":
            obstacles = list(_sim_state.get("obstacles", []))
            obstacles.append(point)
            _sim_state["obstacles"] = obstacles[-16:]
        else:
            trail = list(_sim_state.get("trail", []))
            trail.append(point)
            _sim_state["trail"] = trail[-MAP_TRAIL_LIMIT:]
        return int(now)


def _snapshot_sim_state(now: float) -> tuple[bool, dict[str, object]]:
    with _sim_lock:
        updated_at = float(_sim_state.get("updated_at", 0.0))
        online = (now - updated_at) <= SIM_ONLINE_TIMEOUT_SEC if updated_at > 0 else False
        snapshot = {
            "updated_at": updated_at,
            "telemetry": _sim_state.get("telemetry"),
            "vision": _sim_state.get("vision"),
            "uav_position": _sim_state.get("uav_position"),
            "waypoint_position": _sim_state.get("waypoint_position"),
            "obstacles": list(_sim_state.get("obstacles", [])),
            "trail": list(_sim_state.get("trail", [])),
        }
    return online, snapshot


def _new_mission_id(now: int) -> str:
    return f"mission-{now}"


def _parse_waypoint(command: str) -> str:
    match = re.search(r"waypoint\s+([A-Za-z0-9_-]+)", command, flags=re.IGNORECASE)
    if not match:
        return "A3"
    return match.group(1).upper()


def _parse_altitude(command: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*m", command, flags=re.IGNORECASE)
    if not match:
        return 12.0
    return float(match.group(1))


def _build_objective(command: str, waypoint: str, altitude_m: float) -> str:
    cmd = command.strip().rstrip(".")
    if cmd:
        return f"{cmd}. Maintain {altitude_m:.1f}m and reach waypoint {waypoint}."
    return f"Maintain {altitude_m:.1f}m and reach waypoint {waypoint}."


def _advance_runtime_locked(now: float) -> None:
    if _runtime.status != "running":
        _runtime.last_tick = now
        return

    elapsed = max(0, now - _runtime.last_tick)
    _runtime.progress_sec = min(TOTAL_MISSION_SECONDS, _runtime.progress_sec + elapsed)
    _runtime.last_tick = now

    if _runtime.progress_sec >= TOTAL_MISSION_SECONDS:
        _runtime.status = "completed"


def set_leader_command(command: str) -> dict[str, str | bool]:
    sanitized = command.strip()
    if not sanitized:
        return {
            "accepted": False,
            "command": "",
            "mission_id": _runtime.mission_id,
            "mission_status": _runtime.status,
        }

    now = time.time()
    now_epoch = int(now)
    waypoint = _parse_waypoint(sanitized)
    altitude_m = _parse_altitude(sanitized)

    with _runtime_lock:
        _runtime.mission_id = _new_mission_id(now_epoch)
        _runtime.leader_command = sanitized
        _runtime.assigned_at = now_epoch
        _runtime.status = "ready"
        _runtime.progress_sec = 0.0
        _runtime.last_tick = now
        _runtime.target_waypoint = waypoint
        _runtime.target_altitude_m = altitude_m
        _runtime.objective = _build_objective(sanitized, waypoint, altitude_m)

        return {
            "accepted": True,
            "command": sanitized,
            "mission_id": _runtime.mission_id,
            "mission_status": _runtime.status,
        }


def get_leader_command_state() -> tuple[str, int]:
    with _runtime_lock:
        return _runtime.leader_command, _runtime.assigned_at


def control_mission(action: str) -> dict[str, str | bool]:
    now = time.time()

    with _runtime_lock:
        _advance_runtime_locked(now)

        if action == "start":
            if _runtime.status in {"ready", "paused"}:
                _runtime.status = "running"
                _runtime.last_tick = now
                return {"accepted": True, "status": _runtime.status, "detail": "Mission execution started."}
            if _runtime.status == "running":
                return {"accepted": True, "status": _runtime.status, "detail": "Mission is already running."}
            return {"accepted": False, "status": _runtime.status, "detail": "Assign a mission before start."}

        if action == "resume":
            if _runtime.status == "paused":
                _runtime.status = "running"
                _runtime.last_tick = now
                return {"accepted": True, "status": _runtime.status, "detail": "Mission resumed."}
            return {"accepted": False, "status": _runtime.status, "detail": "Mission is not paused."}

        if action == "pause":
            if _runtime.status == "running":
                _runtime.status = "paused"
                return {"accepted": True, "status": _runtime.status, "detail": "Mission paused."}
            return {"accepted": False, "status": _runtime.status, "detail": "Mission is not running."}

        if action == "abort":
            if _runtime.status in {"running", "paused", "ready"}:
                _runtime.status = "aborted"
                return {"accepted": True, "status": _runtime.status, "detail": "Mission aborted by operator."}
            return {"accepted": False, "status": _runtime.status, "detail": "No active mission to abort."}

        if action == "reset":
            _runtime.status = "idle"
            _runtime.progress_sec = 0.0
            _runtime.last_tick = now
            _runtime.objective = "Awaiting leader mission assignment"
            return {"accepted": True, "status": _runtime.status, "detail": "Follower reset to idle."}

        return {"accepted": False, "status": _runtime.status, "detail": "Unsupported action."}


def _build_phases(active_index: int, mission_status: MissionStatus) -> list[Phase]:
    phases: list[Phase] = []
    for index, (phase_id, name, detail) in enumerate(PHASE_TEMPLATE):
        if mission_status == "completed":
            phase_status: PhaseStatus = "completed"
        elif mission_status == "idle":
            phase_status = "pending"
        elif index < active_index:
            phase_status = "completed"
        elif index == active_index and mission_status in {"ready", "running", "paused", "aborted"}:
            phase_status = "active"
        else:
            phase_status = "pending"
        phases.append(Phase(id=phase_id, name=name, detail=detail, status=phase_status))
    return phases


def get_mission_state(tick: int | None = None) -> MissionState:
    current_tick = time.time() if tick is None else float(tick)
    settings = get_settings()

    with _runtime_lock:
        _advance_runtime_locked(current_tick)
        command_age = int(max(0, current_tick - _runtime.assigned_at))
        leader_command = _runtime.leader_command
        mission_status = _runtime.status
        mission_id = _runtime.mission_id
        objective = _runtime.objective
        waypoint = _runtime.target_waypoint
        target_altitude = _runtime.target_altitude_m
        progress_sec = _runtime.progress_sec

    sim_online, sim_snapshot = _snapshot_sim_state(current_tick)

    active_index = min(int(progress_sec // PHASE_SECONDS), len(PHASE_TEMPLATE) - 1)
    wobble = math.sin(current_tick / 8.0)
    progress = 0.0 if mission_status == "idle" else round((progress_sec / TOTAL_MISSION_SECONDS) * 100, 1)
    progress = max(0.0, min(progress, 100.0))

    running_speed = 6.1 + math.cos(current_tick / 7.0) * 0.9 if mission_status == "running" else 0.0
    battery_base = 86 - int((progress_sec / TOTAL_MISSION_SECONDS) * 28)

    telemetry = Telemetry(
        battery_pct=max(32, battery_base),
        altitude_m=round(target_altitude + (wobble * 0.6 if mission_status == "running" else 0.0), 1),
        speed_ms=round(max(0.0, running_speed), 1),
        confidence=round(0.88 + math.sin(current_tick / 13.0) * 0.04, 2),
    )

    if sim_online and isinstance(sim_snapshot.get("telemetry"), dict):
        sim_t = sim_snapshot["telemetry"]
        telemetry = Telemetry(
            battery_pct=int(sim_t["battery_pct"]),
            altitude_m=float(sim_t["altitude_m"]),
            speed_ms=float(sim_t["speed_ms"]),
            confidence=float(sim_t["confidence"]),
        )

    mission_mode = [
        "Command parsing",
        "Formation align",
        "Visual tracking",
        "Avoidance replan",
        "Objective execute",
        "Post-action standby",
    ][active_index] if mission_status != "idle" else "Idle"

    if mission_status == "aborted":
        mission_mode = "Abort hold"
    elif mission_status == "completed":
        mission_mode = "Mission complete"
    elif mission_status == "paused":
        mission_mode = "Paused"
    elif mission_status == "ready":
        mission_mode = "Ready to launch"

    reasoning_trace = [
        f"Leader uplink parsed ({command_age}s ago): {leader_command}",
        f"Mission status: {mission_status} | Mission ID: {mission_id}",
        "eSIM vision feed stable at 24 FPS equivalent stream.",
        "Lite-VLM detected leader intent keywords: formation, altitude, waypoint.",
        f"Current follower mode: {mission_mode}.",
    ]

    if mission_status == "idle":
        follower_thoughts = [
            "No assigned mission. Waiting for leader command.",
            "Maintaining safe hover and low-power perception mode.",
            "Ready to parse next task packet immediately.",
        ]
    elif mission_status == "aborted":
        follower_thoughts = [
            "Abort received. Entering safe hold and canceling active path.",
            "Propulsion set to minimal drift-correction mode.",
            "Awaiting either reset or new mission assignment.",
        ]
    else:
        follower_thoughts = [
            f"Objective: {objective}",
            "Intent decoded: maintain offset from virtual leader trajectory.",
            "Perception confidence high enough for autonomous continuation.",
            f"Tracking waypoint {waypoint} at {target_altitude:.1f}m target altitude.",
            "Prepared to accept next command override from leader channel.",
        ]

    esim_vision = {
        "feed": "NVIDIA eSIM edge stream",
        "scene_summary": "Leader absent physically; virtual trajectory anchor projected ahead.",
        "risk_level": "medium" if mission_status == "running" and active_index in {2, 3} else "low",
        "frame_url": None,
        "stream_url": settings.default_vision_stream_url or None,
        "detected_objects": [
            {"label": "Tree cluster", "distance_m": round(max(6.0, 14.2 - progress_sec / 22.0), 1), "confidence": 0.91},
            {"label": "Power line", "distance_m": round(max(8.0, 22.8 - progress_sec / 25.0), 1), "confidence": 0.83},
            {"label": f"Waypoint marker {waypoint}", "distance_m": round(max(2.0, 31.4 - progress_sec / 5.0), 1), "confidence": 0.95},
        ],
    }

    if sim_online and isinstance(sim_snapshot.get("vision"), dict):
        sim_v = sim_snapshot["vision"]
        esim_vision = {
            "feed": "NVIDIA eSIM live stream",
            "scene_summary": str(sim_v.get("scene_summary", esim_vision["scene_summary"])),
            "risk_level": str(sim_v.get("risk_level", esim_vision["risk_level"])),
            "frame_url": sim_v.get("frame_url"),
            "stream_url": sim_v.get("stream_url", esim_vision["stream_url"]),
            "detected_objects": sim_v.get("detected_objects", esim_vision["detected_objects"]),
        }

    map_2d = {
        "uav": sim_snapshot["uav_position"],
        "waypoint": sim_snapshot["waypoint_position"],
        "obstacles": sim_snapshot["obstacles"],
        "trail": sim_snapshot["trail"],
        "source": "esim-live" if sim_online else "runtime-sim",
    }

    vlm_profile = {
        "name": "NanoVLM-0.5B",
        "runtime": "NVIDIA eSIM edge",
        "latency_ms": 58,
        "context_tokens": 512,
        "mode": "intent-grounded navigation",
    }

    follower_status = {
        "uav_id": "swarm-follower-01",
        "state": mission_mode,
        "mission_status": mission_status,
        "mission_id": mission_id,
        "objective": objective,
        "target_waypoint": waypoint,
        "formation_slot": "left-wing",
        "leader_link": "manual command bridge",
            "health": "nominal" if telemetry.battery_pct > 35 else "battery-low",
    }

    swarm_context = {
        "swarm_id": "alpha-swarm",
        "leader_source": "operator command console",
        "leader_command": leader_command,
        "command_age_sec": command_age,
        "follower_count": 1,
            "vision_link": "live" if sim_online else "simulated",
    }

    checklist = [
        {"name": "Leader command received", "done": mission_status != "idle"},
        {"name": "Mission started", "done": mission_status in {"running", "paused", "aborted", "completed"}},
        {"name": "Formation slot aligned", "done": active_index >= 1 and mission_status != "idle"},
        {"name": "Waypoint objective executed", "done": active_index >= 4 and mission_status != "idle"},
        {"name": "Completion report sent", "done": mission_status == "completed"},
    ]

    remaining = 0 if mission_status in {"idle", "completed", "aborted"} else int(max(0, TOTAL_MISSION_SECONDS - progress_sec))
    mission_state_label = f"{mission_mode} ({PHASE_TEMPLATE[active_index][2]})"

    return MissionState(
        title="Swarm Follower UAV Demo - NVIDIA eSIM",
        progress_label=f"{progress}%",
        phases=_build_phases(active_index, mission_status),
        telemetry=telemetry,
        mission_state=mission_state_label,
        time_remaining_sec=remaining,
        reasoning_trace=reasoning_trace,
        checklist=checklist,
        swarm_context=swarm_context,
        follower_status=follower_status,
        esim_vision=esim_vision,
        map_2d=map_2d,
        vlm_profile=vlm_profile,
        follower_thoughts=follower_thoughts,
    )


def mission_state_as_dict(state: MissionState) -> dict[str, object]:
    return asdict(state)
