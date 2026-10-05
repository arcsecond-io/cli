"""A local copy of the sky-brightness map.

Arcsecond.local shows how dark the sky is at an observing site. By default
the backend reads that out of a map kept on statics.arcsecond.io, a small
range at a time: one more outside connection, and one whose requests say
roughly where the site is. With a copy on this machine there is none.

`arcsecond setup` offers the download once. The answer is the
SKY_BRIGHTNESS_GEOTIFF_PATH line of .env: the copy's path as the backend sees
it, or empty for "asked, and declined" — the backend then keeps to the
outside map, and setup does not ask again.
"""

import os
from pathlib import Path

import click
import httpx

from .utils import _read_env_value, _set_env_value

ENV_KEY = "SKY_BRIGHTNESS_GEOTIFF_PATH"
MAP_URL = "https://statics.arcsecond.io/data/skybrightness/skyglow_2024.tif"
MAP_SIZE = "48 MB"
# Under SHARED_DATA_PATH on this machine, which the backend sees as /data.
RELATIVE_PATH = Path("skybrightness") / "skyglow_2024.tif"
CONTAINER_PATH = "/data/skybrightness/skyglow_2024.tif"

LATER = "arcsecond setup --with-sky-map"


def download(target: Path, url: str = MAP_URL) -> None:
    """Fetch the map to ``target``, through a .partial file so that a copy cut
    short is never mistaken for the map."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    with httpx.stream("GET", url, timeout=60, follow_redirects=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length") or 0) or None
        with open(partial, "wb") as handle, click.progressbar(
            length=total, label="Downloading the sky-brightness map"
        ) as bar:
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                handle.write(chunk)
                bar.update(len(chunk))
    os.replace(partial, target)


def offer(env_path, flag=None, interactive=True) -> None:
    """Ask once whether to keep a local copy of the map, and act on the answer.

    ``flag`` is --with-sky-map / --without-sky-map: it wins over a recorded
    answer. With neither a flag nor a recorded answer nor a terminal to ask
    on, nothing is decided and the next setup asks.
    """
    recorded = _read_env_value(ENV_KEY, env_path)
    if flag is None:
        if recorded is not None:
            return
        if not interactive:
            click.echo(
                "The sky-brightness map is read from statics.arcsecond.io. "
                f"For a copy on this machine instead:  {LATER}"
            )
            return
        flag = click.confirm(
            f"Download the sky-brightness map ({MAP_SIZE}) to this machine? "
            "Without it, the darkness of a site's sky is looked up on statics.arcsecond.io",
            default=True,
        )

    if not flag:
        _set_env_value(env_path, ENV_KEY, "")
        click.echo("Sky brightness will be looked up on statics.arcsecond.io.")
        return

    shared = _read_env_value("SHARED_DATA_PATH", env_path)
    if not shared:
        click.echo(f"No SHARED_DATA_PATH in .env yet, so no place for the map. Later:  {LATER}")
        return
    target = Path(shared) / RELATIVE_PATH
    if not target.exists():
        try:
            download(target)
        except (httpx.HTTPError, OSError) as e:
            # Nothing recorded: the next setup offers it again.
            click.echo(
                f"The sky-brightness map could not be downloaded ({type(e).__name__}: {e}). "
                f"Nothing is lost: it is looked up online meanwhile. Try again with:  {LATER}"
            )
            return
    _set_env_value(env_path, ENV_KEY, CONTAINER_PATH)
    click.echo(f"Sky-brightness map kept at {target}. No outside lookup is made for it.")
