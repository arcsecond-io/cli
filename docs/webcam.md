---
sidebar: true
---

# Live-Image Proxy

The Arcsecond CLI ships a native live-image proxy that lets
[Arcsecond.local](https://www.arcsecond.io) — the self-hosted version of
Arcsecond — access **USB webcams** and **all-sky cameras** attached to (or
visible from) the host machine.

Docker Desktop on Windows and macOS does not forward USB devices into
containers, and may not have access to host filesystem paths where all-sky
software writes its images. The proxy solves both: it runs natively on the
host, where it has direct USB access and can read local files, and exposes
the feeds over HTTP and WebSocket. The Arcsecond backend container reaches
the proxy via `host.docker.internal`.

## Installation

The proxy requires extra dependencies (OpenCV and aiohttp) that are not
installed by default. Install them with the `webcam` extra:

```bash
pip install arcsecond[webcam]
```

The extra is named `webcam` for backward compatibility, but it covers
all-sky support too.

::: tip
If your shell treats square brackets specially (e.g. zsh), quote the package
name:

```bash
pip install 'arcsecond[webcam]'
```

:::

::: warning Windows users — use PowerShell, not WSL
On Windows, the Arcsecond CLI **must be installed and run natively using
PowerShell** (or the standard Windows Command Prompt). Do **not** use the Bash
shell that comes with WSL (Windows Subsystem for Linux).

WSL runs in a virtualised Linux environment that does not have direct access to
the host's USB devices. As a result, the webcam proxy cannot see cameras
attached to the Windows machine when launched from inside WSL.
:::

## USB webcams

### Detecting

```bash
arcsecond webcam detect
```

This probes device indices 0 through 9 and prints the resolution and frame
rate of each camera found.

### Starting the proxy

```bash
arcsecond webcam start [--port 8765] [--host 0.0.0.0] [--log-level INFO]
```

## All-sky cameras

The proxy supports all-sky cameras whose driver software writes JPEG images
to disk. The two most common stacks are auto-discovered:

- **Thomas Jacquin's allsky** ([github.com/AllskyTeam/allsky](https://github.com/AllskyTeam/allsky)),
  typically on a Raspberry Pi
- **indi-allsky** ([github.com/aaronwmorris/indi-allsky](https://github.com/aaronwmorris/indi-allsky)),
  INDI-based

### Detecting

```bash
arcsecond allsky detect
```

This checks well-known paths:

| Path                                                | Software       |
|-----------------------------------------------------|----------------|
| `~/allsky/tmp/image.jpg`                            | Jacquin allsky |
| `/var/www/html/allsky/current/tmp/image.jpg`        | Jacquin allsky |
| `/var/lib/indi-allsky/images/latest.jpg`            | indi-allsky    |
| `~/indi-allsky/latest.jpg`                          | indi-allsky    |

### Starting with custom paths

If your software writes JPEGs to a non-standard location, register them
explicitly. `--allsky` is repeatable; the value can be a file path or a
glob (newest mtime wins):

```bash
arcsecond allsky start \
  --allsky roof=/srv/allsky/latest.jpg \
  --allsky garden='/var/data/allsky/*.jpg'
```

`arcsecond webcam start` accepts the same `--allsky` flag — both commands
launch the same proxy.

## Endpoints

The proxy exposes three endpoints:

| Endpoint        | Method    | Description                                     |
|-----------------|-----------|-------------------------------------------------|
| `/health`       | GET       | Liveness check (`{"status": "ok"}`)             |
| `/detect`       | GET       | JSON list of available sources (webcam + allsky) |
| `/stream/{id}`  | WebSocket | Continuous JPEG frame stream                    |

Source ids look like `webcam:0` or `allsky:roof`. Bare numeric ids
(`/stream/0`) are accepted for backward compatibility and treated as
`webcam:N`.

Press `Ctrl-C` to stop the proxy.

## Connecting Arcsecond.local

No extra configuration is needed when the proxy runs on the same machine as
Arcsecond.local. The backend defaults to `http://host.docker.internal:8765`,
so it can reach the proxy out of the box.

The typical workflow is:

1. Start the proxy on the host: `arcsecond webcam start` (or `arcsecond allsky start`)
2. Start Arcsecond.local: `docker compose up -d`
3. The backend automatically detects and streams from the host sources.

### Remote proxy

If the cameras are attached to a different machine on the same network (e.g.
a dome PC), start the proxy there and set `LIVE_IMAGE_PROXY_URL` in the
`.env` file used by `docker-compose.yml`:

```
LIVE_IMAGE_PROXY_URL=http://192.168.1.42:8765
```

Replace `192.168.1.42` with the actual IP address or hostname. When this
variable is not set, the backend falls back to
`http://host.docker.internal:8765` (the Docker way of saying
`http://localhost:8765` from within a container).

The previous variable name `WEBCAM_PROXY_URL` is still accepted as a
deprecated fallback.

## Stream protocol

Each frame is sent as a JSON message over the WebSocket connection:

```json
{
  "type": "frame",
  "format": "jpeg/base64",
  "data": "<base64-encoded JPEG>"
}
```

For webcams, frames arrive at ~10 fps. For all-sky sources, a frame is sent
only when the source file's mtime changes — typically every 30–120 seconds,
depending on the camera's exposure cadence.

If the source becomes unavailable (device unplugged, file removed) the proxy
sends an error message before closing the connection:

```json
{
  "type": "error",
  "message": "Cannot open webcam at device index 0."
}
```
