import click

from arcsecond.api import ArcsecondConfig
from arcsecond.cloud.uploader import (
    DatasetFileUploader,
    DatasetUploadContext,
)
from arcsecond.cloud.uploader.datafiles.utils import (
    display_upload_datafiles_command_summary,
)
from arcsecond.cloud.uploader.walker import walk_folder_and_upload_files
from arcsecond.options import State, basic_options

pass_state = click.make_pass_decorator(State, ensure=True)


@click.command()
@click.argument("folder", required=True, nargs=1)
@click.option(
    "-d",
    "--dataset",
    required=True,
    nargs=1,
    type=click.STRING,
    help="The UUID or name of the dataset to put data in. If new, it will be created.",
)
@click.option(
    "-t",
    "--telescope",
    required=True,
    nargs=1,
    type=click.UUID,
    help="The telescope UUID, to be attached to the dataset.",
)
@click.option(
    "--raw",
    required=False,
    nargs=1,
    type=click.BOOL,
    help="A flag indicating the data is raw or not. Default True.",
)
@click.option(
    "--tags",
    required=False,
    nargs=1,
    help="An optional list of custom tags to be attached to every filed.",
)
@click.option(
    "-p",
    "--portal",
    required=False,
    nargs=1,
    type=click.STRING,
    help="The portal subdomain, if uploading for an Observatory Portal.",
)
@basic_options
@pass_state
def upload_data(
    state, folder, dataset=None, telescope=None, raw=None, tags=None, portal=None
):
    """
    Upload the data files contained in a folder.

    You will be prompted for confirmation before the whole walking process actually
    start.

    Warning: this method allows to upload a folder with a **consistent** raw data flag as well
    as common custom tags, both applied to every single file. If you want to upload a mixed-content
    folder, you must write your own script.

    Every DataFile must belong to a Dataset. If you provide a Dataset UUID, Arcsecond will
    append files to the dataset. If you provide a Dataset *name*, Arcsecond will try to find
    an existing Dataset with that name. If none could be found, Arcsecond will create one,
    and put files in it.

    You can use `arcsecond datasets [OPTIONS]` to get a list of your existing datasets
    (with their UUID).

    Every Dataset must be attached to a Telescope. This is necessary to retrieve geographical
    coordinates, hence compute local dates, and simply organise datasets. You can use the command
    `arcsecond telescopes [-p subdomain]` to obtain the list of telescopes attached to your
    account or portal.

    Upon validation, Arcsecond will then start walking through the folder tree and uploads regular
    files (hidden and empty files will always be skipped).
    """
    config = ArcsecondConfig.from_state(state)
    context = DatasetUploadContext(
        config,
        input_dataset_uuid_or_name=dataset,
        input_telescope_uuid=telescope,
        org_subdomain=portal,
        is_raw_data=raw,
        custom_tags=tags,
    )

    context.validate()

    display_upload_datafiles_command_summary(
        context,
        [
            folder,
        ],
    )
    ok = input("\n   ----> OK? (Press Enter) ")
    if ok.strip() == "":
        walk_folder_and_upload_files(DatasetFileUploader, context, folder)
