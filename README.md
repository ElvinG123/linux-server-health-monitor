# Linux Server Health Monitor

A small Python command-line tool that records basic health information for a Linux host and checks TCP connectivity to configured endpoints. Each run prints a summary and can append a record to a local history file.

## Checks

- Hostname and collection time in UTC
- Uptime and memory usage from `/proc`
- System load average and root filesystem usage
- Non-loopback network interface state from `/sys`
- TCP connection status and connection time for configured host and port pairs

The script uses only the Python standard library.

## Requirements

- Python 3.10 or newer
- Linux for the full system report

On macOS, disk usage, load average, and TCP checks may work, but Linux-specific uptime, memory, and interface data will show as unavailable.

## Quick start

From the project directory:

```bash
cp config.example.json config.json
python3 healthcheck.py --config config.json
```

The example configuration checks `example.com` on port `443`. Edit `config.json` to use endpoints you own or are authorized to check. The script attempts a TCP connection only to each configured host and port; it does not discover or scan devices.

Example configuration:

```json
{
  "tcp_checks": [
    {
      "name": "Management service",
      "host": "192.0.2.20",
      "port": 443
    },
    {
      "name": "SSH service",
      "host": "192.0.2.21",
      "port": 22
    }
  ]
}
```

The addresses above are documentation examples. Replace them with authorized endpoints.

## Repeated checks

Take ten snapshots, ten seconds apart:

```bash
python3 healthcheck.py --config config.json --interval 10 --count 10
```

Run every 60 seconds until stopped with `Ctrl+C`:

```bash
python3 healthcheck.py --config config.json --interval 60
```

Print JSON instead of the terminal summary:

```bash
python3 healthcheck.py --config config.json --json --no-log
```

## Output

By default, each snapshot is appended to `data/health_history.jsonl`, with one JSON object per line. Use `--no-log` to skip saving history or `--output path/to/file.jsonl` to choose another path.

The overall status is `WARN` if a configured TCP connection fails or all detected non-loopback interfaces are down. A failed TCP check means the connection could not be established during that attempt; it does not identify the cause or confirm whether an application is healthy.

`config.json` and files under `data/` are excluded from Git so local settings and results are not committed.
