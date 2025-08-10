import pathlib

import click

from arcsecond.cloud.uploader.utils import (
    __get_formatted_bytes_size,
    __get_formatted_size_times,
    is_file_hidden,
)

from .context import DatasetUploadContext


def _display_user_and_key(context: DatasetUploadContext):
    """Displays user and key information."""
    key = (
        f"(Upload key: {context.config.upload_key[:4]}••••)"
        if context.config.upload_key
        else f"(Access key: {context.config.access_key[:4]}••••)"
    )
    click.echo(f" • Arcsecond username: @{context.config.username} {key}")


def _display_subdomain_info(context: DatasetUploadContext):
    """Displays subdomain upload information."""
    msg = (
        f" • Uploading to Observatory Portal '{context.subdomain}'."
        if context.subdomain
        else " • Uploading to your *personal* account."
    )
    click.echo(msg)


def _display_dataset_info(context: DatasetUploadContext):
    """Displays dataset-related information."""
    if context.dataset_uuid and context.dataset_name:
        msg = f" • Data will be appended to existing dataset '{context.dataset_name}' ({context.dataset_uuid})."
    elif not context.dataset_uuid and context.dataset_name:
        msg = f" • Data will be inserted into a new dataset named '{context.dataset_name}'."
    else:
        msg = " • Using folder names for dataset names (one folder = one dataset)."
    click.echo(msg)


def _display_data_type_info(context: DatasetUploadContext):
    """Displays the type of data being uploaded."""
    msg = f" • Data is considered as {'RAW' if context.is_raw_data else 'NOT RAW'}."
    click.echo(msg)


def _display_custom_tags_info(context: DatasetUploadContext):
    """Displays custom tags information."""
    msg = (
        f" • Data files will be tagged with the following custom tags: {context.custom_tags}."
        if context.custom_tags
        else " • Data files will receive no custom tags."
    )
    click.echo(msg)


def _display_telescope_info(context: DatasetUploadContext):
    """Displays telescope-related information."""
    if context.telescope:
        msg = f" • Dataset will be attached to the telescope named '{context.telescope.get('name')}' ({context.telescope.get('uuid')})."
        click.echo(msg)
    elif not context.dataset_uuid and context.dataset_name:
        msg = " • Dataset will not be attached to any telescope. It can be changed later in the web."
        click.echo(msg)


def _display_api_server_info(context: DatasetUploadContext):
    """Displays API server information."""
    click.echo(
        f" • Using API server: '{context.config.api_name}' ({context.config.api_server})"
    )


def _display_folders_summary(folders: list):
    """Displays summary information about the folders being uploaded."""
    click.echo(f" • Folder{'s' if len(folders) > 1 else ''}:")
    for folder in folders:
        folder_path = pathlib.Path(folder).expanduser().resolve()
        _display_folder_path(folder_path)
        _display_folder_warning(folder_path)
        _display_folder_size(folder_path)


def _display_folder_path(folder_path: pathlib.Path):
    """Displays the folder path."""
    click.echo(
        f"   > Path: {str(folder_path.parent if folder_path.is_file() else folder_path)}"
    )


def _display_folder_warning(folder_path: pathlib.Path):
    """Displays warnings if the folder is the HOME folder."""
    if folder_path == pathlib.Path.home():
        click.echo("   >>> Warning: This folder is your HOME folder. <<<")


def _display_folder_size(folder_path: pathlib.Path):
    """Calculates and displays the folder size and estimated upload time."""
    size = sum(
        f.stat().st_size
        for f in folder_path.glob("**/*")
        if f.is_file() and not is_file_hidden(f)
    )
    click.echo(
        f"   > Volume: {__get_formatted_bytes_size(size)} in total in this folder."
    )
    click.echo(f"   > Estimated upload time: {__get_formatted_size_times(size)}")


def display_upload_datafiles_command_summary(
    context: DatasetUploadContext, folders: list
):
    """Displays a summary of the upload command."""
    click.echo("\n --- Upload summary --- ")
    _display_user_and_key(context)
    _display_subdomain_info(context)
    _display_dataset_info(context)
    _display_data_type_info(context)
    _display_custom_tags_info(context)
    _display_telescope_info(context)
    _display_api_server_info(context)
    _display_folders_summary(folders)
