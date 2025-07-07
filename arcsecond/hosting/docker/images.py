from concurrent.futures import ThreadPoolExecutor, as_completed

import click
import docker
from docker.errors import APIError
from docker.errors import ImageNotFound
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from .constants import DOCKER_IMAGE_CONTAINERS_NAMES

console = Console()


def has_docker_image(full_name):
    name, tag = full_name.split(':')
    click.echo(f'Checking for Docker image {name}:{tag}...')
    client = docker.from_env()
    try:
        client.images.get(f'{name}:{tag}')
    except ImageNotFound:
        return False
    except APIError:
        # Print log
        return False
    else:
        return True


def has_all_arcsecond_docker_images():
    image_names = set([im for (im, _, _) in DOCKER_IMAGE_CONTAINERS_NAMES.values()])
    return all([has_docker_image(name) for name in image_names])


def update_docker_image(full_name: str, progress, task_id):
    name, tag = full_name.split(':')
    image_ref = f"oci.pkg.keygen.sh/arcsecond/{name}"
    client = docker.from_env()
    layer_totals = {}
    layer_currents = {}

    try:
        resp = client.api.pull(image_ref, tag=tag, stream=True, decode=True)
        for line in resp:
            layer_id = line.get("id")
            details = line.get("progressDetail", {})
            status = line.get("status", "")

            if not layer_id or 'current' not in details or 'total' not in details:
                continue  # Skip uninformative lines

            # Track per-layer progress
            total = details['total']
            current = details['current']
            layer_totals[layer_id] = total
            layer_currents[layer_id] = current

            # Compute total image download progress
            total_bytes = sum(layer_totals.values())
            current_bytes = sum(min(layer_currents.get(k, 0), v) for k, v in layer_totals.items())

            if total_bytes > 0:
                progress.update(task_id, completed=current_bytes, total=total_bytes)

        progress.update(task_id, description=f"[green]{image_ref}:{tag} - Pulled[/green]")
        progress.stop_task(task_id)
        return True
    except APIError as e:
        print(str(e))
        progress.update(task_id, description=f"[red]{image_ref}:{tag} - Failed[/red]")
        progress.stop_task(task_id)
        return False


def pull_images_concurrently(images):
    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True,
    ) as progress:

        task_ids = {
            image: progress.add_task(f"[cyan]{image}[/cyan] - Starting", start=True)
            for image in images
        }

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(update_docker_image, image, progress, task_ids[image]): image
                for image in images
            }
            for future in as_completed(futures):
                image = futures[future]
                try:
                    success = future.result()
                    if success:
                        console.print(f"✅ [green]Pulled {image}[/green]")
                    else:
                        console.print(f"❌ [red]Failed to pull {image}[/red]")
                except Exception as exc:
                    console.print(f"🔥 [bold red]Exception pulling {image}:[/bold red] {exc}")


def pull_all_arcsecond_docker_images():
    image_names = set([im for (im, _, _) in DOCKER_IMAGE_CONTAINERS_NAMES.values()])
    pull_images_concurrently(image_names)
