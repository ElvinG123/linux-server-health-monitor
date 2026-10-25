# Linux Server Health Monitor

A small, dependency-free Python utility for collecting a health snapshot from a Linux server. It reports basic host resources, Linux network interface state, and TCP reachability for endpoints you explicitly list in a JSON config file. It appends each snapshot to a local JSON Lines history file.

This is a portfolio project for demonstrating Linux command-line familiarity, Python scripting, basic monitoring, network troubleshooting, and readable operational documentation. It does not scan networks or discover devices.

## What it checks

- Hostname and UTC collection time
- System uptime, load average, and memory usage from Linux `/proc`
- Root filesystem usage
- Non-loopback interface operational state from Linux sysfs
- TCP connectivity and connection time for configured host and port pairs
- Human-readable terminal summary or structured JSON output
- Append-only JSONL history for later review

## Requirements

- Linux
- Python 3.10 or newer
- No third-party Python packages

## Quick start

```bash
cd linux-server-health-monitor
cp config.example.json config.json
python3 healthcheck.py --config config.json
```

Edit `config.json` and replace the example endpoint with a service you are authorized to check, such as a server or management endpoint assigned to you. Each check makes one TCP connection attempt to the exact configured host and port.

Example configuration:

```json
{
  "tcp_checks": [
    {"name": "Management service", "host": "192.0.2.20", "port": 443},
    {"name": "SSH service", "host": "192.0.2.21", "port": 22}
  ]
}
```

The addresses above are documentation-only examples; replace them with endpoints you are authorized to check.

## Run continuously

Take one snapshot every 60 seconds, up to 10 times:

```bash
python3 healthcheck.py --config config.json --interval 60 --count 10
```

Run until stopped with `Ctrl+C`:

```bash
python3 healthcheck.py --config config.json --interval 60
```

Print structured JSON and choose a separate history file:

```bash
python3 healthcheck.py --config config.json --json --output data/demo.jsonl
```

Print without writing history:

```bash
python3 healthcheck.py --config config.json --no-log
```

## Output

The default report is designed for a quick terminal check. Every run also appends one JSON object per line to `data/health_history.jsonl`. The `data/` directory is ignored by Git so machine-specific history is not committed.

The overall status is `WARN` when a configured TCP check fails or when no non-loopback interface reports `up`. A failed check only means that the target did not accept a TCP connection during that attempt; firewall policy, service state, routing, DNS, and temporary packet loss can all affect the result.

## Suggested portfolio improvements

For a polished GitHub project, add a short README screenshot of a sample run, describe what each check can and cannot tell you, and include a sample JSONL record with any real hostnames or addresses removed. Keep the config file free of production hostnames, IPs, credentials, and customer details.

## Resume wording

After you have run the project and understand how it works, you can list it under **Projects**:

**Linux Server Health Monitor** | Python, Linux

- Built a dependency-free Python utility that records Linux host health, including memory, disk, uptime, load average, and network interface state.
- Added configurable TCP connectivity checks with latency reporting and JSONL history for reviewing repeated results.

Be ready to explain how `/proc` and `/sys` provide Linux system information, how the TCP check works, and what a failed connection does and does not prove. Do not claim production deployment or customer use; this project is a personal lab tool.
