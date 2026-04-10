---
sidebar: true
---

# Webcam Proxy

The Arcsecond CLI includes a native webcam proxy that lets
[Arcsecond.local](https://www.arcsecond.io) — the self-hosted version of
Arcsecond — access USB webcams attached to the host machine.

Docker Desktop on Windows and macOS does not forward USB devices into
containers. The proxy solves this by running natively on the host (where it
has direct USB access) and exposing the camera feeds over HTTP and WebSocket.
The Arcsecond backend container then reaches the proxy via
`host.docker.internal`.

## Installation

Webcam support requires extra dependencies (OpenCV and aiohttp) that are not
installed by default. Install them with the `webcam` extra:

```bash
pip install arcsecond[webcam]
```

If you already have the Arcsecond CLI installed and want to add webcam support:

```bash
pip install --upgrade arcsecond[webcam]
```

::: tip
If your shell treats square brackets specially (e.g. zsh), quote the package
name:

```bash
pip install 'arcsecond[webcam]'
```

:::

## Detecting webcams

To scan for locally attached webcams:

```bash
arcsecond webcam detect
```

This probes device indices 0 through 9 and prints the resolution and frame
rate of each camera found.

## Starting the proxy server

```bash
arcsecond webcam start [--port 8765] [--host 0.0.0.0] [--log-level INFO]
```

The server exposes three endpoints:

| Endpoint          | Method    | Description                         |
|-------------------|-----------|-------------------------------------|
| `/health`         | GET       | Liveness check (`{"status": "ok"}`) |
| `/detect`         | GET       | JSON list of attached webcams       |
| `/stream/{index}` | WebSocket | Continuous JPEG frame stream        |

Press `Ctrl-C` to stop the proxy.

## Connecting Arcsecond.local

No extra configuration is needed when the proxy runs on the same machine as
Arcsecond.local. The backend defaults to `http://host.docker.internal:8765`,
so it can reach the proxy out of the box.

The typical workflow is:

1. Start the proxy on the host: `arcsecond webcam start`
2. Start Arcsecond.local: `docker compose up -d`
3. The backend automatically detects and streams from the host webcams.

### Remote webcam proxy

If the webcams are attached to a different machine on the same network (e.g.
a dome PC), start the proxy there and set `WEBCAM_PROXY_URL` in the `.env`
file used by `docker-compose.yml`:

```
WEBCAM_PROXY_URL=http://192.168.1.42:8765
```

Replace `192.168.1.42` with the actual IP address or hostname of the machine
running the proxy. When this variable is not set, the backend falls back to
`http://host.docker.internal:8765` (which is the Docker way of saying 
`http://localhost:8765` from within a container.)

## Stream protocol

Each frame is sent as a JSON message over the WebSocket connection:

```json
{
  "type": "frame",
  "format": "jpeg/base64",
  "data": "<base64-encoded JPEG>"
}
```

If the webcam device is lost (e.g. unplugged), the proxy sends an error
message before closing the connection:

```json
{
  "type": "error",
  "message": "Device lost at index 0."
}
```
