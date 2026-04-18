import { useEffect, useMemo, useState } from "react";
import "./UavDashboard.css";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

type PhaseStatus = "pending" | "active" | "completed";

type MissionPhase = {
  id: number;
  name: string;
  detail: string;
  status: PhaseStatus;
};

type MissionPayload = {
  title: string;
  progress_label: string;
  phases: MissionPhase[];
  telemetry: {
    battery_pct: number;
    altitude_m: number;
    speed_ms: number;
    confidence: number;
  };
  mission_state: string;
  time_remaining_sec: number;
  checklist: { name: string; done: boolean }[];
  swarm_context: {
    swarm_id: string;
    leader_source: string;
    leader_command: string;
    command_age_sec: number;
    follower_count: number;
  };
  follower_status: {
    uav_id: string;
    state: string;
    mission_status: "idle" | "ready" | "running" | "paused" | "aborted" | "completed";
    mission_id: string;
    objective: string;
    target_waypoint: string;
    formation_slot: string;
    leader_link: string;
    health: string;
  };
  esim_vision: {
    feed: string;
    scene_summary: string;
    risk_level: string;
    frame_url?: string | null;
    stream_url?: string | null;
    detected_objects: { label: string; distance_m: number; confidence: number }[];
  };
  map_2d: {
    uav: { x: number; y: number };
    waypoint: { x: number; y: number };
    obstacles: { x: number; y: number }[];
    trail: { x: number; y: number }[];
    source: string;
  };
  vlm_profile: {
    name: string;
    runtime: string;
    latency_ms: number;
    context_tokens: number;
    mode: string;
  };
  follower_thoughts: string[];
};

const FALLBACK_DATA: MissionPayload = {
  title: "Swarm Follower UAV Demo - NVIDIA eSIM",
  progress_label: "16.7%",
  phases: [
    { id: 1, name: "PHASE 1", detail: "Acquire leader command", status: "active" },
    { id: 2, name: "PHASE 2", detail: "Align formation slot", status: "pending" },
    { id: 3, name: "PHASE 3", detail: "Track corridor and obstacles", status: "pending" },
    { id: 4, name: "PHASE 4", detail: "Micro-replan and hold spacing", status: "pending" },
    { id: 5, name: "PHASE 5", detail: "Execute waypoint objective", status: "pending" },
    { id: 6, name: "PHASE 6", detail: "Report completion and await next", status: "pending" },
  ],
  telemetry: { battery_pct: 74, altitude_m: 12.4, speed_ms: 6.2, confidence: 0.94 },
  mission_state: "PHASE 1 (Acquire leader command)",
  time_remaining_sec: 177,
  checklist: [
    { name: "Leader command received", done: true },
    { name: "Safety envelope clear", done: true },
    { name: "Vision feed locked", done: true },
    { name: "Map trail synced", done: false },
    { name: "Mission handoff prepared", done: false },
  ],
  swarm_context: {
    swarm_id: "SWARM-ALPHA",
    leader_source: "Manual operator input",
    leader_command: "Follow the leader and keep safe spacing.",
    command_age_sec: 9,
    follower_count: 4,
  },
  follower_status: {
    uav_id: "UAV-02",
    state: "tracking",
    mission_status: "running",
    mission_id: "MIS-2204",
    objective: "Shadow leader route",
    target_waypoint: "WP-B7",
    formation_slot: "Left-Rear",
    leader_link: "Healthy",
    health: "Nominal",
  },
  esim_vision: {
    feed: "NVIDIA eSIM live stream",
    scene_summary: "Leader corridor clear; obstacle cluster remains on the right flank.",
    risk_level: "moderate",
    frame_url: null,
    stream_url: null,
    detected_objects: [
      { label: "Leader UAV", distance_m: 18.2, confidence: 0.97 },
      { label: "Obstacle Cluster", distance_m: 6.3, confidence: 0.81 },
    ],
  },
  map_2d: {
    uav: { x: 48, y: 55 },
    waypoint: { x: 72, y: 28 },
    obstacles: [
      { x: 60, y: 42 },
      { x: 66, y: 50 },
      { x: 77, y: 36 },
    ],
    trail: [
      { x: 16, y: 78 },
      { x: 25, y: 70 },
      { x: 34, y: 64 },
      { x: 42, y: 58 },
      { x: 48, y: 55 },
      { x: 58, y: 47 },
      { x: 66, y: 39 },
    ],
    source: "NVIDIA eSIM",
  },
  vlm_profile: {
    name: "VLM-Scout",
    runtime: "Realtime",
    latency_ms: 84,
    context_tokens: 8192,
    mode: "vision+trajectory",
  },
  follower_thoughts: [
    "Waiting for backend stream...",
    "Leader route aligned with corridor.",
    "Obstacle avoidance margin looks stable.",
  ],
};

function phaseClass(status: PhaseStatus): string {
  if (status === "completed") {
    return "phase-chip completed";
  }
  if (status === "active") {
    return "phase-chip active";
  }
  return "phase-chip pending";
}

export default function UavDashboard() {
  const [data, setData] = useState<MissionPayload>(FALLBACK_DATA);
  const [leaderCommand, setLeaderCommand] = useState("");
  const [commandStatus, setCommandStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    const loadState = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/mission-state`);
        if (!response.ok) {
          throw new Error(`Request failed ${response.status}`);
        }
        const payload = (await response.json()) as MissionPayload;
        if (!cancelled) {
          setData(payload);
          setError("");
        }
      } catch {
        if (!cancelled) {
          setError("Backend unavailable. Showing fallback mission state.");
        }
      }
    };

    loadState();
    const intervalId = window.setInterval(loadState, 2500);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, []);

  const submitLeaderCommand = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const command = leaderCommand.trim();
    if (!command) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/leader-command`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command }),
      });
      if (!response.ok) {
        throw new Error(`Request failed ${response.status}`);
      }
      const payload = (await response.json()) as { mission_id: string; mission_status: string };
      setCommandStatus(`Mission ${payload.mission_id} assigned (${payload.mission_status}).`);
      setError("");
    } catch {
      setCommandStatus("Cannot send command. Backend is offline.");
    }
  };

  const controlMission = async (action: "start" | "pause" | "resume" | "abort") => {
    try {
      const response = await fetch(`${API_BASE}/api/mission/control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (!response.ok) {
        throw new Error(`Request failed ${response.status}`);
      }
      const payload = (await response.json()) as { detail: string; status: string };
      setCommandStatus(`${payload.detail} (status=${payload.status})`);
      setError("");
    } catch {
      setCommandStatus("Mission control failed. Backend is offline.");
    }
  };

  const startAction = data.follower_status.mission_status === "paused" ? "resume" : "start";
  const startLabel = data.follower_status.mission_status === "paused" ? "RESUME MISSION" : "START MISSION";

  const phaseItems = useMemo(
    () =>
      data.phases.map((phase, index) => (
        <div className="phase-item" key={phase.id}>
          <div className={phaseClass(phase.status)}>
            <div className="phase-title">{phase.name}</div>
            <div className="phase-detail">{phase.detail}</div>
          </div>
          {index < data.phases.length - 1 && <div className="phase-arrow">&gt;</div>}
        </div>
      )),
    [data.phases],
  );

  const trailPath = useMemo(() => {
    const points = data.map_2d.trail;
    if (points.length === 0) {
      return "";
    }
    return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  }, [data.map_2d.trail]);

  return (
    <main className="dashboard">
      <header className="header">
        <h1>
          {data.title} <span className="badge">MVP Demo</span>
        </h1>
        {error && <p className="error-line">{error}</p>}
      </header>

      <section className="top-row">
        <section className="top-card">
          <div className="mission-progress-title">Swarm Mission Progress</div>
          <div className="phase-wrap">{phaseItems}</div>
        </section>

        <section className="leader-console panel">
          <div className="leader-heading">
            <h2>Leader Command Console</h2>
            <span className="leader-meta">Source: Manual operator input</span>
          </div>
          <form className="leader-form" onSubmit={submitLeaderCommand}>
            <textarea
              value={leaderCommand}
              onChange={(event) => setLeaderCommand(event.target.value)}
              rows={2}
              placeholder="Example: Leader: Move to waypoint B7, maintain 10m altitude, avoid east corridor."
            />
            <button type="submit">SEND</button>
          </form>
          <div className="leader-status-row compact">
            <span>Swarm: {data.swarm_context.swarm_id}</span>
            <span>WP: {data.follower_status.target_waypoint}</span>
            <span>Status: {data.follower_status.mission_status}</span>
          </div>
          {commandStatus && <p className="command-status">{commandStatus}</p>}
        </section>
      </section>

      <section className="grid-3">
        <section className="col left">
          <h2>eSIM Visual Perception</h2>
          <div className="panel sensor-panel">
            <div className="sensor-main">
              {data.esim_vision.stream_url ? (
                <video src={data.esim_vision.stream_url} className="vision-frame" controls autoPlay muted playsInline />
              ) : data.esim_vision.frame_url ? (
                <img src={data.esim_vision.frame_url} alt="NVIDIA eSIM frame" className="vision-frame" />
              ) : (
                <>
                  <span className="target-box">Virtual Leader Anchor</span>
                  <span className="obs-box left">Risk Left</span>
                  <span className="obs-box right">Risk Right</span>
                </>
              )}
            </div>
            <div className="sensor-grid">
              <div className="sensor-small heat">Feed: {data.esim_vision.feed}</div>
              <div className="sensor-small lidar">Risk: {data.esim_vision.risk_level}</div>
            </div>
            <p className="scene-summary">{data.esim_vision.scene_summary}</p>
            <div className="detected-wrap">
              {data.esim_vision.detected_objects.map((item) => (
                <div className="detected-item" key={item.label}>
                  <strong>{item.label}</strong>
                  <span>{item.distance_m} m</span>
                  <span>{item.confidence}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="col center">
          <h2>Telemetry & Safety</h2>
          <div className="telemetry-safety-layout">
            <div className="telemetry-left">
              <div className="panel map-panel">
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="map-svg">
                  <path d={trailPath} className="map-trail" />
                  {data.map_2d.obstacles.map((obstacle, index) => (
                    <circle key={`obs-${index}`} cx={obstacle.x} cy={obstacle.y} r="1.8" className="map-obstacle" />
                  ))}
                  <circle cx={data.map_2d.waypoint.x} cy={data.map_2d.waypoint.y} r="2.2" className="map-waypoint" />
                  <circle cx={data.map_2d.uav.x} cy={data.map_2d.uav.y} r="2.4" className="map-uav" />
                </svg>
                <div className="home-dot">Map</div>
                <div className="uav-dot">UAV</div>
                <div className="target-dot">WP</div>
              </div>
              <div className="panel checklist">
                {data.checklist.map((item) => (
                  <div className={`check-row ${item.done ? "done" : "todo"}`} key={item.name}>
                    {item.done ? "[x]" : "[ ]"} {item.name}
                  </div>
                ))}
              </div>
            </div>
            <div className="telemetry-right">
              <div className="metric-card">
                <div className="metric-title">Battery</div>
                <div className="metric-value">{data.telemetry.battery_pct}%</div>
                <div className="metric-subtle">Stable</div>
              </div>
              <div className="metric-card">
                <div className="metric-title">Altitude</div>
                <div className="metric-value">{data.telemetry.altitude_m} m</div>
              </div>
              <div className="metric-card">
                <div className="metric-title">Speed</div>
                <div className="metric-value">{data.telemetry.speed_ms} m/s</div>
              </div>
              <div className="metric-card">
                <div className="metric-title">Mission State</div>
                <div className="metric-value small">{data.mission_state}</div>
                <div className="metric-subtle">Time left: {data.time_remaining_sec}s</div>
              </div>
              <div className="metric-card">
                <div className="metric-title">Localization Confidence</div>
                <div className="metric-value">{data.telemetry.confidence}</div>
              </div>
              <div className="metric-card">
                <div className="metric-title">Follower Status</div>
                <div className="metric-value small">{data.follower_status.state}</div>
                <div className="metric-subtle">Slot: {data.follower_status.formation_slot}</div>
              </div>
              <div className="metric-card">
                <div className="metric-title">Mission Runtime</div>
                <div className="metric-value small">{data.follower_status.mission_status.toUpperCase()}</div>
                <div className="metric-subtle">ID: {data.follower_status.mission_id}</div>
              </div>
              <div className="metric-card">
                <div className="metric-title">Map Source</div>
                <div className="metric-value small">{data.map_2d.source}</div>
                <div className="metric-subtle">Trail points: {data.map_2d.trail.length}</div>
              </div>
              <div className="metric-card">
                <div className="metric-title">VLM</div>
                <div className="metric-value small">{data.vlm_profile.name}</div>
                <div className="metric-subtle">
                  {data.vlm_profile.latency_ms}ms / {data.vlm_profile.context_tokens} tok
                </div>
              </div>
            </div>
          </div>
          <div className="control-wrap">
            <button type="button" onClick={() => controlMission(startAction)}>
              {startLabel}
            </button>
            <button type="button" onClick={() => controlMission("pause")}>PAUSE FOLLOWER</button>
            <button type="button" className="danger" onClick={() => controlMission("abort")}>ABORT MISSION</button>
          </div>
        </section>

        <section className="col right">
          <h2>Follower Thought Stream</h2>
          <div className="panel log-container">
            {data.follower_thoughts.map((line, index) => (
              <div className="log-row" key={`${index}-${line}`}>
                - {line}
              </div>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}