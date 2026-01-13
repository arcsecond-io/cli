import os
import re

import click

email_regex = re.compile(
    r"([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+"
)


def _validate_value_base(value):
    if len(value.strip()) < 3:
        raise click.BadParameter("Value must be at least 3 characters long.")
    return value.strip()


def _validate_subdomain(value):
    value = _validate_value_base(value).lower()
    if not re.match(r"[a-z\-_]{3,}", value):
        raise click.BadParameter(
            "Value must be a correct subdomain (no special characters except - or _)"
        )
    return value


def _validate_email_host_item(value):
    value = _validate_value_base(value)
    if value[0] == "$":
        value = os.environ[value[1:]].lower()
        click.echo("Value: " + value)
    return value


def __validate_email_host(value):
    value = _validate_email_host_item(value)
    if not re.match(r"[a-z\-_]+(\.[a-z\-_]+)?", value):
        raise click.BadParameter(
            "Value must be a correct email host name (no http://, only the hostname)."
        )
    return value


def _validate_email_admin(value):
    value = _validate_value_base(value)
    if not re.fullmatch(email_regex, value):
        raise click.BadParameter("Value must be a correct email address.")
    return value
