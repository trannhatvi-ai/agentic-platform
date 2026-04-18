from __future__ import annotations

import argparse
import random
import time

import httpx


def post_json(client: httpx.Client, url: str, payload: dict[str, object]) -> None:
    response = client.post(url, json=payload, timeout=5.0)
    response.raise_for_status()


def run_bridge(api_base: str, interval_sec: float) -> None:
    """Example bridge that forwards simulated eSIM streams to the backend.

    Replace the synthetic generators with your NVIDIA eSIM subscriptions.
    """
    step = 0
    with httpx.Client() as client:
        while True:
            step += 1
            telemetry = {
                "battery_pct": max(25.0, 90.0 - step * 0.06),
                "altitude_m": 10.0 + random.uniform(-0.7, 0.7),
                "speed_ms": max(0.0, 6.0 + random.uniform(-1.0, 1.0)),
                "confidence": min(1.0, max(0.0, 0.9 + random.uniform(-0.04, 0.04))),
            }

            vision = {
                "scene_summary": "eSIM frame: corridor tracking with dynamic obstacles",
                "risk_level": random.choice(["low", "medium", "medium"]),
                "stream_url": None,
                "frame_url": None,
                "detected_objects": [
                    {"label": "tree", "distance_m": round(random.uniform(8, 18), 1), "confidence": 0.91},
                    {"label": "wire", "distance_m": round(random.uniform(14, 26), 1), "confidence": 0.82},
                ],
            }

            # X moves right, Y oscillates for a simple 2D trajectory.
            uav_x = min(95.0, 12.0 + step * 0.35)
            uav_y = 50.0 + 12.0 * (0.5 - random.random())
            map_point = {"x": round(uav_x, 2), "y": round(uav_y, 2), "tag": "uav"}

            post_json(client, f"{api_base}/api/sim/telemetry", telemetry)
            post_json(client, f"{api_base}/api/sim/vision", vision)
            post_json(client, f"{api_base}/api/sim/map-point", map_point)

            print(
                f"[bridge] telemetry={telemetry['battery_pct']:.1f}%/{telemetry['speed_ms']:.1f}mps "
                f"map=({map_point['x']}, {map_point['y']})"
            )
            time.sleep(interval_sec)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge NVIDIA eSIM-like streams into API")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="Backend API base URL")
    parser.add_argument("--interval", type=float, default=0.25, help="Push interval in seconds")
    args = parser.parse_args()
    run_bridge(api_base=args.api_base.rstrip("/"), interval_sec=max(0.05, args.interval))


if __name__ == "__main__":
    main()
