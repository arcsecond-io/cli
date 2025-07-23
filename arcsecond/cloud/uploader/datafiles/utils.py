import pathlib

import click

from arcsecond.cloud.uploader.utils import (
    __get_formatted_bytes_size,
    __get_formatted_size_times,
    is_file_hidden,
)

from .context import DatasetUploadContext


def display_upload_datafiles_command_summary(
    context: DatasetUploadContext, folders: list
):
    click.echo("\n --- Upload summary --- ")
    key = (
        f"(Upload key: {context.config.upload_key[:4]}••••)"
        if context.config.upload_key
        else f"(Access key: {context.config.access_key[:4]}••••)"
    )
    click.echo(f" • Arcsecond username: @{context.config.username} {key}")
    if context.subdomain:
        msg = f" • Uploading to Observatory Portal '{context.subdomain}'."
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

    msg = f" • Data is considered as {'RAW' if context.is_raw_data else 'NOT RAW'}."
    click.echo(msg)

    if context.custom_tags:
        msg = f" • Data files will be tagged with the following custom tags: {context.custom_tags}."
    else:
        msg = " • Data files will receive no custom tags."
    click.echo(msg)

    if context.telescope:
        msg = f" • Dataset will be attached to the telescope named '{context.telescope.get('name')}' ({context.telescope.get('uuid')})."
        click.echo(msg)
    else:
        if not context.dataset_uuid and context.dataset_name:
            msg = " • Dataset will not be attached to any telescope. It can be changed later in the web."
            click.echo(msg)

    click.echo(
        f" • Using API server: '{context.config.api_name}' ({context.config.api_server})"
    )
    click.echo(f" • Folder{'s' if len(folders) > 1 else ''}:")
    for folder in folders:
        folder_path = pathlib.Path(folder).expanduser().resolve()
        click.echo(
            f"   > Path: {str(folder_path.parent if folder_path.is_file() else folder_path)}"
        )

        if folder_path == pathlib.Path.home():
            click.echo("   >>> Warning: This folder is your HOME folder. <<<")

        size = sum(
            f.stat().st_size
            for f in folder_path.glob("**/*")
            if f.is_file() and not is_file_hidden(f)
        )
        click.echo(
            f"   > Volume: {__get_formatted_bytes_size(size)} in total in this folder."
        )
        click.echo(f"   > Estimated upload time: {__get_formatted_size_times(size)}")
