import pathlib

import click

from arcsecond.cloud.uploader.utils import (
    __get_formatted_bytes_size,
    __get_formatted_size_times,
    is_file_hidden,
)

from .context import AllSkyCameraImageUploadContext


def display_upload_allskycameraimages_command_summary(
    context: AllSkyCameraImageUploadContext, folders: list
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

    msg = f" • Data will be attached to camera '{context.camera_name}' ({context.camera_uuid})."
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
