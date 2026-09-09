"""Tests for the proxy's HTTP surface: the loopback guard, and /sources.

/sources is what lets a camera registered or forgotten while the proxy is up
take effect without a restart. It answers only to callers on the same machine,
so the guard is tested here as carefully as the endpoint itself.
"""

import asyncio

import pytest

from arcsecond.imagesources.store import NET, USB, Camera

NETCAM = {"id": "abc", "kind": "net", "url": "rtsp://cam.local/s"}


def _proxy_app(cameras=None):
    from arcsecond.imagesources.proxy import build_app

    return build_app(cameras)


def _run_against_proxy(body, cameras=None):
    from aiohttp import web

    async def _main():
        app = _proxy_app(cameras)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", 0).start()
        port = runner.addresses[0][1]
        try:
            return await body(f"http://127.0.0.1:{port}", app["registry"])
        finally:
            await runner.cleanup()

    return asyncio.run(_main())


# ---------------------------------------------------------------------------
# The loopback guard
# ---------------------------------------------------------------------------


def test_a_forged_forwarded_header_does_not_grant_access():
    """The guard must read the socket peer, never a header the caller controls."""
    from arcsecond.imagesources.proxy import _is_loopback

    class FakeRequest:
        remote = "203.0.113.9"
        headers = {"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1"}

    assert _is_loopback(FakeRequest()) is False


@pytest.mark.parametrize("remote", ["127.0.0.1", "::1"])
def test_loopback_addresses_are_recognised(remote):
    from arcsecond.imagesources.proxy import _is_loopback

    class FakeRequest:
        headers = {}

    request = FakeRequest()
    request.remote = remote
    assert _is_loopback(request) is True


@pytest.mark.parametrize("remote", ["203.0.113.9", "10.0.0.4", None, "not-an-ip"])
def test_non_loopback_addresses_are_refused(remote):
    from arcsecond.imagesources.proxy import _is_loopback

    class FakeRequest:
        headers = {}

    request = FakeRequest()
    request.remote = remote
    assert _is_loopback(request) is False


# ---------------------------------------------------------------------------
# /sources
# ---------------------------------------------------------------------------


def test_a_loopback_caller_may_register():
    import aiohttp

    async def body(base, registry):
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{base}/sources", json={"cameras": [NETCAM]}) as r:
                return r.status, await r.json(), len(registry.cameras)

    status, payload, count = _run_against_proxy(body)
    assert status == 200
    assert payload["added"] == ["abc"]
    assert count == 1


def test_every_kind_of_camera_can_be_registered_over_the_endpoint():
    import aiohttp

    payload = {
        "cameras": [
            NETCAM,
            {"id": "def", "kind": "usb", "index": 0},
            {"id": "ghi", "kind": "allsky", "path": "/a.jpg"},
            {"id": "jkl", "kind": "allsky", "url": "http://sky.local/latest.jpg"},
        ]
    }

    async def body(base, registry):
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{base}/sources", json=payload) as r:
                return await r.json(), {c.id for c in registry.cameras}

    answer, ids = _run_against_proxy(body)
    assert answer["added"] == ["abc", "def", "ghi", "jkl"]
    assert ids == {"abc", "def", "ghi", "jkl"}


@pytest.mark.parametrize(
    "payload",
    [
        {"cameras": [{"id": "abc", "kind": "net"}]},  # no url
        {"cameras": [{"kind": "net", "url": "rtsp://c/s"}]},  # no id
        {"cameras": [{"id": "abc", "kind": "telescope"}]},  # not a camera
        {"cameras": []},
        {"netcam": [{"id": "dome", "url": "rtsp://c/s"}]},  # the old shape
    ],
)
def test_a_malformed_registration_is_rejected(payload):
    import aiohttp

    async def body(base, registry):
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{base}/sources", json=payload) as r:
                return r.status, len(registry.cameras)

    status, count = _run_against_proxy(body)
    assert status == 400
    assert count == 0


def test_a_camera_can_be_removed_by_the_id_that_was_printed():
    import aiohttp

    async def body(base, registry):
        async with aiohttp.ClientSession() as s:
            await s.post(f"{base}/sources", json={"cameras": [NETCAM]})
            async with s.delete(f"{base}/sources/abc") as r:
                return r.status, await r.json(), len(registry.cameras)

    status, payload, count = _run_against_proxy(body)
    assert status == 200
    assert payload["removed"] is True
    assert count == 0


def test_removing_an_unregistered_camera_says_so_without_failing():
    import aiohttp

    async def body(base, registry):
        async with aiohttp.ClientSession() as s:
            async with s.delete(f"{base}/sources/zzz") as r:
                return r.status, await r.json()

    status, payload = _run_against_proxy(body)
    assert status == 200
    assert payload["removed"] is False


# ---------------------------------------------------------------------------
# /detect
# ---------------------------------------------------------------------------


def test_detect_lists_what_is_registered_and_probes_nothing():
    import aiohttp

    cameras = [
        Camera(id="abc", kind=NET, url="rtsp://admin:hunter2@cam.local/s"),
        Camera(id="def", kind=USB, index=0, label="Guide cam"),
    ]

    async def body(base, registry):
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{base}/detect") as r:
                return await r.json()

    served = _run_against_proxy(body, cameras=cameras)
    assert [item["id"] for item in served] == ["abc", "def"]
    # Both are webcams on the wire; only the transport differs.
    assert {item["kind"] for item in served} == {"webcam"}
    assert {item["extra"]["transport"] for item in served} == {"rtsp", "usb"}
    assert "hunter2" not in str(served)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def test_health_tells_a_local_caller_which_process_it_is():
    """`proxy stop` signals this pid rather than the one in the runtime file."""
    import os

    import aiohttp

    async def body(base, registry):
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{base}/health") as r:
                return await r.json()

    answer = _run_against_proxy(body)
    assert answer["status"] == "ok"
    assert answer["pid"] == os.getpid()


def test_health_does_not_tell_the_network_which_process_it_is():
    from arcsecond.imagesources.proxy import handle_health

    class FakeRequest:
        remote = "203.0.113.9"
        headers = {}

    answer = asyncio.run(handle_health(FakeRequest()))
    assert b'"status": "ok"' in answer.body
    assert b"pid" not in answer.body


# ---------------------------------------------------------------------------
# Shutting down
#
# aiohttp waits for in-flight handlers before it finishes, and the streaming
# handler loops until its socket closes. Without the shutdown hook the proxy
# ignores Ctrl-C and `proxy stop` for as long as anyone is watching.
# ---------------------------------------------------------------------------


def test_a_viewer_is_registered_while_it_streams_and_dropped_after():
    import aiohttp

    async def body(base, registry, app, image):
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(f"{base}/stream/abc".replace("http", "ws")) as ws:
                await asyncio.wait_for(ws.receive(), 5)
                during = len(app["websockets"])
            # The handler notices the socket has gone on its next poll.
            for _ in range(50):
                if not app["websockets"]:
                    break
                await asyncio.sleep(0.05)
            return during, len(app["websockets"])

    during, after = _run_with_allsky(body)
    assert during == 1
    assert after == 0


def test_shutdown_sends_every_viewer_away():
    """The fix for a proxy that would not stop while somebody was watching."""
    import aiohttp

    async def body(base, registry, app, image):
        async with aiohttp.ClientSession() as s:
            ws = await s.ws_connect(f"{base}/stream/abc".replace("http", "ws"))
            await asyncio.wait_for(ws.receive(), 5)
            assert len(app["websockets"]) == 1

            await app.shutdown()  # what Ctrl-C and `proxy stop` trigger

            closing = await asyncio.wait_for(ws.receive(), 5)
            await ws.close()
            return closing.type

    assert _run_with_allsky(body) in (
        aiohttp.WSMsgType.CLOSE,
        aiohttp.WSMsgType.CLOSING,
        aiohttp.WSMsgType.CLOSED,
    )


def test_closing_viewers_copes_with_one_that_has_already_gone():
    from arcsecond.imagesources.proxy import _close_websockets

    class GoneWebSocket:
        async def close(self, **kwargs):
            raise ConnectionResetError("already gone")

    app = {"websockets": {GoneWebSocket()}}
    with pytest.raises(ConnectionResetError):
        asyncio.run(_close_websockets(app))


def _run_with_allsky(body):
    """Run ``body`` against a proxy serving one all-sky camera from a temp file."""
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from aiohttp import web

    from arcsecond.imagesources.sources.filewatch import FileWatchSource
    from arcsecond.imagesources.store import ALLSKY

    async def _main():
        # A real all-sky camera is polled every few seconds. Nothing here is
        # about that cadence, and waiting through it would make the shutdown
        # tests take longer than the shutdown they are checking.
        with (
            patch.object(FileWatchSource, "poll_interval", 0.05),
            tempfile.TemporaryDirectory() as tmp,
        ):
            image = Path(tmp) / "latest.jpg"
            image.write_bytes(b"\xff\xd8 not really a jpeg \xff\xd9")
            app = _proxy_app([Camera(id="abc", kind=ALLSKY, path=str(image))])
            runner = web.AppRunner(app)
            await runner.setup()
            await web.TCPSite(runner, "127.0.0.1", 0).start()
            port = runner.addresses[0][1]
            try:
                return await body(
                    f"http://127.0.0.1:{port}", app["registry"], app, image
                )
            finally:
                await runner.cleanup()

    return asyncio.run(_main())
