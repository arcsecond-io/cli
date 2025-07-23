import click

from arcsecond.api import ArcsecondAPI, ArcsecondConfig
from arcsecond.errors import ArcsecondError
from arcsecond.options import State, basic_options

pass_state = click.make_pass_decorator(State, ensure=True)


@click.command(help="Display the list of (portal) datasets.")
@click.option(
    "-p",
    "--portal",
    required=False,
    nargs=1,
    help="The portal subdomain, if uploading for an Observatory Portal.",
)
@basic_options
@pass_state
def datasets(state, portal=None):
    org_subdomain = portal or ""
    if org_subdomain:
        click.echo(f" • Fetching datasets for portal '{org_subdomain}'...")
    else:
        click.echo(" • Fetching datasets...")

    dataset_list, error = ArcsecondAPI(
        ArcsecondConfig.from_state(state), org_subdomain
    ).datasets.list()
    if error is not None:
        raise ArcsecondError(str(error))

    if isinstance(dataset_list, dict) and "results" in dataset_list.keys():
        dataset_list = dataset_list["results"]

    click.echo(
        f" • Found {len(dataset_list)} dataset{'s' if len(dataset_list) > 1 else ''}."
    )
    for dataset_dict in dataset_list:
        s = f" 💾 \"{dataset_dict['name']}\" "
        s += f"(uuid: {dataset_dict['uuid']}) "
        s += f"(telescope: {dataset_dict['telescope']}) "
        s += f"(files: {dataset_dict['data_files_count']}) "
        click.echo(s)


@click.command(help="Display the list of (portal) telescopes.")
@click.option(
    "-p",
    "--portal",
    required=False,
    nargs=1,
    help="The portal subdomain, if uploading for an Observatory Portal.",
)
@basic_options
@pass_state
def telescopes(state, portal=None):
    org_subdomain = portal or ""
    if org_subdomain:
        click.echo(f" • Fetching telescopes for portal '{org_subdomain}'...")
    else:
        click.echo(" • Fetching telescopes...")

    telescope_list, error = ArcsecondAPI(
        ArcsecondConfig.from_state(state), org_subdomain
    ).telescopes.list()
    if error is not None:
        raise ArcsecondError(str(error))

    if isinstance(telescope_list, dict) and "results" in telescope_list.keys():
        telescope_list = telescope_list["results"]

    click.echo(
        f" • Found {len(telescope_list)} telescope{'s' if len(telescope_list) > 1 else ''}."
    )
    for telescope_dict in telescope_list:
        s = f" 💾 \"{telescope_dict['name']}\" "
        s += f"(uuid: {telescope_dict['uuid']}) "
        s += f"[ObservingSite UUID: {telescope_dict['observing_site']}]"
        click.echo(s)


@click.command(help="Display the list of (portal) all-sky cameras.")
@click.option(
    "-p",
    "--portal",
    required=False,
    nargs=1,
    help="The portal subdomain, if uploading for an Observatory Portal.",
)
@basic_options
@pass_state
def allskycameras(state, portal=None):
    org_subdomain = portal or ""
    if org_subdomain:
        click.echo(f" • Fetching allskycameras for portal '{org_subdomain}'...")
    else:
        click.echo(" • Fetching allskycameras...")

    cameras_list, error = ArcsecondAPI(
        ArcsecondConfig.from_state(state), org_subdomain
    ).allskycameras.list()
    if error is not None:
        raise ArcsecondError(str(error))

    if isinstance(cameras_list, dict) and "results" in cameras_list.keys():
        cameras_list = cameras_list["results"]

    click.echo(
        f" • Found {len(cameras_list)} all-sky camera{'s' if len(cameras_list) > 1 else ''}."
    )
    for camera_list in cameras_list:
        s = f" 💾 \"{camera_list['name']}\" "
        s += f"(uuid: {camera_list['uuid']}) "
        click.echo(s)
