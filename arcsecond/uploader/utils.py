import math
import pathlib

import click

from .context import UploadContext


def is_file_hidden(path):
    return any([part for part in path.parts if len(part) > 0 and part[0] == '.'])


def __get_formatted_time(seconds):
    if seconds > 86400:
        return f"{seconds / 86400:.1f}d"
    elif seconds > 3600:
        return f"{seconds / 3600:.1f}h"
    elif seconds > 60:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds:.1f}s"


def __get_formatted_size_times(size):
    total = f"{__get_formatted_time(size / pow(10, 4))} on 10 kB/s, "
    total += f"{__get_formatted_time(size / pow(10, 5))} on 100 kB/s, "
    total += f"{__get_formatted_time(size / pow(10, 6))} on 1 MB/s, "
    total += f"{__get_formatted_time(size / pow(10, 7))} on 10 MB/s"
    return total


def __get_formatted_bytes_size(size):
    if size == 0:
        return '0 Bytes'
    k = 1024
    units = ['Bytes', 'kB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    i = math.floor(math.log10(1.0 * size) / math.log10(k))
    return f"{(size / math.pow(k, i)):.2f} {units[i]}"


def display_command_summary(context: UploadContext, folders: list):
    click.echo("\n --- Upload summary --- ")
    click.echo(f" • Arcsecond username: @{context.config.username} (Upload key: {context.config.upload_key[:4]}••••)")
    if context.organisation_subdomain:
        role = context.config.read_key(context.organisation_subdomain)
        msg = f" • Uploading to Observatory Portal '{context.organisation_subdomain}'."
    else:
        msg = " • Uploading to your *personal* account."
    click.echo(msg)

    if context.dataset_uuid and context.dataset_name:
        msg = f" • Data will be appended to existing dataset '{context.dataset_name}' ({context.dataset_uuid})."
    elif not context.dataset_uuid and context.dataset_name:
        msg = f" • Data will be inserted into a new dataset named '{context.dataset_name}'."
    else:
        # This is not supposed to happen anymore.
        msg = " • Using folder names for dataset names (one folder = one dataset)."
    click.echo(msg)

    if context.telescope:
        msg = f" • Dataset will be attached to the telescope named '{context.telescope.get('name')}' ({context.telescope.get('uuid')})."
        click.echo(msg)
    else:
        if not context.dataset_uuid and context.dataset_name:
            msg = " • Dataset will not be attached to any telescope. It can be changed later in the web."
            click.echo(msg)

    click.echo(f" • Using API server: '{context.config.api_name}' ({context.config.api_server})")
    click.echo(f" • Folder{'s' if len(folders) > 1 else ''}:")
    for folder in folders:
        folder_path = pathlib.Path(folder).expanduser().resolve()
        click.echo(f"   > Path: {str(folder_path.parent if folder_path.is_file() else folder_path)}")

        if folder_path == pathlib.Path.home():
            click.echo("   >>> Warning: This folder is your HOME folder. <<<")

        size = sum(f.stat().st_size for f in folder_path.glob('**/*') if f.is_file() and not is_file_hidden(f))
        click.echo(f"   > Volume: {__get_formatted_bytes_size(size)} in total in this folder.")
        click.echo(f"   > Estimated upload time: {__get_formatted_size_times(size)}")
