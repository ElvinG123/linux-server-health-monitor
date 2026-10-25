#!/usr/bin/env python3
"""Collect a lightweight health snapshot for one Linux host.

Network checks are limited to the host and TCP port entries explicitly listed
in the JSON configuration file. This tool does not discover or scan hosts.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path(__file__).with_name("config.example.json")
DEFAULT_OUTPUT = Path(__file__).with_name("data") / "health_history.jsonl"


def read_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    targets = config.get("tcp_checks", [])
    if not isinstance(targets, list):
        raise ValueError("'tcp_checks' must be a list")
    for index, target in enumerate(targets):
        if not isinstance(target, dict):
            raise ValueError(f"tcp_checks[{index}] must be an object")
        host = target.get("host")
        port = target.get("port")
        if not isinstance(host, str) or not host.strip():
            raise ValueError(f"tcp_checks[{index}].host must be a non-empty string")
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise ValueError(f"tcp_checks[{index}].port must be an integer from 1 to 65535")
    return config


def linux_memory() -> dict[str, int] | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        return None

    values: dict[str, int] = {}
    for line in meminfo.read_text(encoding="utf-8").splitlines():
        key, _, remainder = line.partition(":")
        if key in {"MemTotal", "MemAvailable"}:
            fields = remainder.split()
            if fields:
                values[key] = int(fields[0])
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if not total or available is None:
        return None
    used = total - available
    return {
        "total_mb": round(total / 1024),
        "used_mb": round(used / 1024),
        "used_percent": round(used / total * 100, 1),
    }


def linux_uptime_seconds() -> int | None:
    uptime_file = Path("/proc/uptime")
    if not uptime_file.is_file():
        return None
    return int(float(uptime_file.read_text(encoding="utf-8").split()[0]))


def interface_status() -> list[dict[str, str]] | None:
    net_dir = Path("/sys/class/net")
    if not net_dir.is_dir():
        return None

    interfaces = []
    for interface in sorted(net_dir.iterdir()):
        if interface.name == "lo":
            continue
        try:
            admin_state = (interface / "flags").read_text(encoding="utf-8").strip()
            oper_state = (interface / "operstate").read_text(encoding="utf-8").strip()
        except OSError:
            admin_state, oper_state = "unknown", "unknown"
        interfaces.append({
            "name": interface.name,
            "admin_flags": admin_state,
            "oper_state": oper_state,
        })
    return interfaces


def tcp_check(target: dict[str, Any], timeout: float) -> dict[str, Any]:
    host = target["host"].strip()
    port = target["port"]
    label = str(target.get("name") or f"{host}:{port}")
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        return {
            "name": label,
            "host": host,
            "port": port,
            "status": "UP",
            "latency_ms": elapsed_ms,
        }
    except (OSError, TimeoutError) as exc:
        return {
            "name": label,
            "host": host,
            "port": port,
            "status": "DOWN",
            "error": str(exc),
        }


def collect_snapshot(config: dict[str, Any], timeout: float) -> dict[str, Any]:
    load_average = None
    if hasattr(os, "getloadavg"):
        load_average = [round(value, 2) for value in os.getloadavg()]

    disk = shutil.disk_usage("/")
    disk_percent = round(disk.used / disk.total * 100, 1) if disk.total else None
    memory = linux_memory()
    interfaces = interface_status()
    tcp_results = [tcp_check(target, timeout) for target in config.get("tcp_checks", [])]

    interface_warning = bool(interfaces) and not any(
        item["oper_state"] == "up" for item in interfaces
    )
    failed_tcp_checks = sum(item["status"] == "DOWN" for item in tcp_results)
    status = "OK"
    if failed_tcp_checks or interface_warning:
        status = "WARN"

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hostname": socket.gethostname(),
        "platform": sys.platform,
        "overall_status": status,
        "system": {
            "load_average_1_5_15": load_average,
            "memory": memory,
            "uptime_seconds": linux_uptime_seconds(),
            "root_disk": {
                "total_gb": round(disk.total / (1024 ** 3), 2),
                "used_gb": round(disk.used / (1024 ** 3), 2),
                "used_percent": disk_percent,
            },
        },
        "network": {
            "interfaces": interfaces,
            "tcp_checks": tcp_results,
        },
    }


def format_uptime(seconds: int | None) -> str:
    if seconds is None:
        return "unavailable"
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    return f"{days}d {hours}h {minutes}m"


def print_report(snapshot: dict[str, Any]) -> None:
    system = snapshot["system"]
    disk = system["root_disk"]
    print(f"[{snapshot['overall_status']}] {snapshot['hostname']}  {snapshot['timestamp_utc']}")
    print(f"  Uptime: {format_uptime(system['uptime_seconds'])}")
    print(f"  Root disk: {disk['used_gb']:.2f}/{disk['total_gb']:.2f} GB ({disk['used_percent']:.1f}% used)")

    memory = system["memory"]
    if memory:
        print(f"  Memory: {memory['used_mb']}/{memory['total_mb']} MB ({memory['used_percent']:.1f}% used)")
    else:
        print("  Memory: unavailable (Linux /proc/meminfo not found)")

    load = system["load_average_1_5_15"]
    if load:
        print(f"  Load average (1/5/15 min): {load[0]} / {load[1]} / {load[2]}")

    interfaces = snapshot["network"]["interfaces"]
    if interfaces is None:
        print("  Interfaces: unavailable (Linux sysfs not found)")
    elif not interfaces:
        print("  Interfaces: no non-loopback interfaces found")
    else:
        states = ", ".join(f"{item['name']}={item['oper_state']}" for item in interfaces)
        print(f"  Interfaces: {states}")

    checks = snapshot["network"]["tcp_checks"]
    if checks:
        print("  Configured TCP checks:")
        for check in checks:
            detail = f"{check['latency_ms']} ms" if check["status"] == "UP" else check.get("error", "unreachable")
            print(f"    {check['status']}: {check['name']} ({detail})")
    else:
        print("  Configured TCP checks: none (edit config.example.json to add endpoints)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="JSON config file")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="JSONL history file")
    parser.add_argument("--interval", type=float, default=0, help="repeat every N seconds; 0 means run once")
    parser.add_argument("--count", type=int, default=0, help="number of snapshots; 0 means repeat until Ctrl+C")
    parser.add_argument("--timeout", type=float, default=2.0, help="TCP connection timeout in seconds")
    parser.add_argument("--no-log", action="store_true", help="print results without writing a history file")
    parser.add_argument("--json", action="store_true", help="print each snapshot as formatted JSON")
    args = parser.parse_args()

    if args.interval < 0 or args.timeout <= 0 or args.count < 0:
        parser.error("interval and count must be non-negative, and timeout must be positive")
    if args.count > 1 and args.interval == 0:
        parser.error("set --interval when --count is greater than 1")

    try:
        config = read_config(args.config)
    except ValueError as exc:
        parser.error(str(exc))

    snapshots_written = 0
    try:
        while True:
            snapshot = collect_snapshot(config, args.timeout)
            if args.json:
                print(json.dumps(snapshot, indent=2))
            else:
                print_report(snapshot)

            if not args.no_log:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open("a", encoding="utf-8") as history:
                    history.write(json.dumps(snapshot, sort_keys=True) + "\n")
                print(f"  History appended to: {args.output}")

            snapshots_written += 1
            if args.count and snapshots_written >= args.count:
                break
            if args.interval == 0:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
