"""The command reference, generated from the command tree itself.

`arcsecond docs commands --out docs/reference/commands` writes one Markdown page per top-level
command — usage, help, arguments, options, subcommands — plus an index and a
machine-readable `commands.json`, every page carrying the documentation
site's frontmatter with `source: generated`.

It is a command of the tool rather than a script in the documentation
repository on purpose: the reference for version X is then produced by
version X. A documentation build runs `pip install arcsecond==X` and then
this, and a page describing a command that no longer exists, an option
that was renamed or a flag that was removed cannot be written at all —
which is the whole point. Renames and removals are precisely the class of
change a handwritten reference misses.

Hidden commands and options stay out: they are compatibility aliases
(`upload-data`) or plumbing (`--no-banner`), not things to teach.

`--check DIR` compares what would be written against what DIR holds and
fails when they differ, for a continuous-integration job that keeps a
committed copy honest.
"""

import html
import inspect
import json
import textwrap
from pathlib import Path
from typing import List, Optional, Tuple

import click

from . import __version__

INDEX_FILENAME = "index.md"
MANIFEST_FILENAME = "commands.json"

# Who reads a page, per top-level command. Everything not listed is for the
# operator of an Arcsecond.local installation — that is what most of the tool
# is for. The astronomer commands are the ones that talk to a server about
# data, whichever server the pointer names.
ASTRONOMER_COMMANDS = frozenset({"upload", "datasets", "telescopes"})
DEFAULT_AUDIENCE = "operator"


def _escape(text: str) -> str:
    """Prose that is safe in a VitePress page: `<int>` would otherwise be
    read as a tag and `{{` as an interpolation, and either fails the build."""
    return html.escape(text, quote=False).replace("{{", "&#123;&#123;")


def _render_help(text: Optional[str]) -> List[str]:
    """The help text as Markdown paragraphs.

    Click marks a paragraph it must not rewrap with a backspace character —
    that is how command examples are written in a docstring — and such a
    paragraph is exactly what belongs in a code fence here."""
    # Dedented the way click dedents it for --help. Python 3.13 strips a
    # docstring's indentation at compile time and 3.12 does not, so without
    # this the same source generated two different pages depending on the
    # interpreter that ran it.
    text = inspect.cleandoc(text or "")
    lines: List[str] = []
    for paragraph in text.split("\n\n"):
        if not paragraph.strip():
            continue
        if paragraph.lstrip().startswith("\b"):
            code = textwrap.dedent(paragraph.replace("\b", "", 1)).strip("\n")
            lines += ["```", code, "```", ""]
        else:
            lines += [_escape(paragraph.strip()), ""]
    return lines


def _visible_commands(
    group: click.Group, ctx: click.Context
) -> List[Tuple[str, click.Command]]:
    commands = []
    for name in group.list_commands(ctx):
        command = group.get_command(ctx, name)
        if command is not None and not command.hidden:
            commands.append((name, command))
    return commands


def _frontmatter(title: str, audience: str) -> str:
    lines = [
        "---",
        f"title: {json.dumps(title)}",
        "visibility: public",
        f"audience: {audience}",
        "tier: reference",
        "source: generated",
        f"cli: {json.dumps(__version__.__version__)}",
        "---",
        "",
        "",
    ]
    return "\n".join(lines)


def _render_params(command: click.Command, ctx: click.Context) -> List[str]:
    lines: List[str] = []
    arguments = [p for p in command.params if isinstance(p, click.Argument)]
    options = [
        p for p in command.params if isinstance(p, click.Option) and not p.hidden
    ]

    if arguments:
        lines += ["**Arguments**", ""]
        for argument in arguments:
            # Written as the usage line writes it: [NAME] when optional, ... when repeatable.
            shape = argument.human_readable_name
            if not argument.required:
                shape = f"[{shape}]"
            if argument.nargs == -1:
                shape += "..."
            need = "required" if argument.required else "optional"
            lines.append(f"- `{shape}` — {need}")
        lines.append("")

    if options:
        lines += ["**Options**", "", "| Option | Description |", "| --- | --- |"]
        for option in options:
            record = option.get_help_record(ctx)
            if record is None:
                continue
            opts, description = record
            lines.append(f"| `{opts}` | {_escape(description)} |")
        lines.append("")
    return lines


def _render_command(
    path: List[str], command: click.Command, parent: Optional[click.Context], depth: int
) -> List[str]:
    ctx = click.Context(command, info_name=path[-1], parent=parent)
    heading = "#" * min(depth, 6)
    lines = [f"{heading} `{' '.join(path)}`", ""]

    usage = " ".join(path + command.collect_usage_pieces(ctx))
    lines += ["```", usage, "```", ""]

    lines += _render_help(command.help)

    lines += _render_params(command, ctx)

    if isinstance(command, click.Group):
        children = _visible_commands(command, ctx)
        if children:
            lines += ["**Subcommands**", ""]
            for name, child in children:
                summary = _escape(child.get_short_help_str(limit=120))
                lines.append(
                    f"- [`{' '.join(path + [name])}`](#{_anchor(path + [name])}) — {summary}"
                )
            lines.append("")
            for name, child in children:
                lines += _render_command(path + [name], child, ctx, depth + 1)
    return lines


def _anchor(path: List[str]) -> str:
    # VitePress slugifies "`arcsecond api use`" to "arcsecond-api-use".
    return "-".join(path)


def _page_for(name: str, command: click.Command, root_ctx: click.Context) -> str:
    audience = "astronomer" if name in ASTRONOMER_COMMANDS else DEFAULT_AUDIENCE
    body = _render_command(["arcsecond", name], command, root_ctx, depth=1)
    return (
        _frontmatter(f"arcsecond {name}", audience)
        + "\n".join(body).rstrip("\n")
        + "\n"
    )


def _index_for(entries: List[dict]) -> str:
    lines = [
        _frontmatter("Command reference", DEFAULT_AUDIENCE),
        "# Command reference",
        "",
        f"Every command of the `arcsecond` tool, version {__version__.__version__}, "
        "generated from the tool itself.",
        "",
        "| Command | For | What it does |",
        "| --- | --- | --- |",
    ]
    for entry in entries:
        lines.append(
            f"| [`arcsecond {entry['name']}`](./{entry['page']}) | {entry['audience']} | {_escape(entry['summary'])} |"
        )
    return "\n".join(lines) + "\n"


def generate(root: click.Group, program: str = "arcsecond") -> dict:
    """``{relative path: content}`` for the whole reference."""
    root_ctx = click.Context(root, info_name=program)
    files = {}
    entries = []
    for name, command in _visible_commands(root, root_ctx):
        page = f"{name}.md"
        files[page] = _page_for(name, command, root_ctx)
        entries.append(
            {
                "name": name,
                "page": page,
                "audience": (
                    "astronomer" if name in ASTRONOMER_COMMANDS else DEFAULT_AUDIENCE
                ),
                "summary": command.get_short_help_str(limit=120),
                "group": isinstance(command, click.Group),
            }
        )
    files[INDEX_FILENAME] = _index_for(entries)
    files[MANIFEST_FILENAME] = (
        json.dumps(
            {
                "program": program,
                "version": __version__.__version__,
                "commands": entries,
            },
            indent=2,
        )
        + "\n"
    )
    return files


def write(files: dict, out: Path) -> List[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for relative, content in files.items():
        target = out / relative
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written


def differences(files: dict, against: Path) -> List[str]:
    """Paths whose committed copy differs from what would be generated,
    including pages that are missing or left over."""
    changed = []
    for relative, content in files.items():
        target = against / relative
        if not target.exists() or target.read_text(encoding="utf-8") != content:
            changed.append(relative)
    if against.exists():
        for existing in sorted(against.glob("*.md")):
            if existing.name not in files:
                changed.append(existing.name + " (stale)")
    return changed


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


@click.group(
    hidden=True, help="Generate the documentation the tool can describe itself."
)
def docs():
    pass


@docs.command(name="commands", help="Write the command reference as Markdown pages.")
@click.option(
    "--out",
    "out",
    type=click.Path(file_okay=False),
    default=None,
    help="Folder to write into.",
)
@click.option(
    "--check",
    "check",
    type=click.Path(file_okay=False, exists=True),
    default=None,
    help="Compare against this folder instead of writing; exit 1 if it is out of date.",
)
@click.pass_context
def docs_commands(ctx, out, check):
    root = ctx.find_root().command
    files = generate(root)
    if check:
        changed = differences(files, Path(check))
        if changed:
            click.echo("The command reference is out of date:")
            for name in changed:
                click.echo(f"  {name}")
            click.echo("\nRegenerate it:  arcsecond docs commands --out " + check)
            raise SystemExit(1)
        click.echo(f"The command reference in {check} is up to date.")
        return
    if not out:
        raise click.UsageError(
            "Give --out FOLDER to write, or --check FOLDER to verify."
        )
    written = write(files, Path(out))
    click.echo(f"Wrote {len(written)} files to {out}")


@docs.command(
    name="compose",
    help="Write the services and environment reference from the packaged compose template.",
)
@click.option(
    "--out",
    "out",
    type=click.Path(file_okay=False),
    default=None,
    help="Folder to write into.",
)
@click.option(
    "--check",
    "check",
    type=click.Path(file_okay=False, exists=True),
    default=None,
    help="Compare against this folder instead of writing; exit 1 if it is out of date.",
)
def docs_compose(out, check):
    from arcsecond.hosting import composedoc

    files = composedoc.generate(__version__.__version__)
    if check:
        changed = differences(files, Path(check))
        if changed:
            click.echo("The services/environment reference is out of date:")
            for name in changed:
                click.echo(f"  {name}")
            click.echo("\nRegenerate it:  arcsecond docs compose --out " + check)
            raise SystemExit(1)
        click.echo(f"The services/environment reference in {check} is up to date.")
        return
    if not out:
        raise click.UsageError(
            "Give --out FOLDER to write, or --check FOLDER to verify."
        )
    written = write(files, Path(out))
    click.echo(f"Wrote {len(written)} files to {out}")
