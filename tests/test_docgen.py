"""The generated command reference: complete, honest about hidden things,
and safe to drop into the documentation site."""

import json

from click.testing import CliRunner

from arcsecond import __version__, cli, docgen


def _pages():
    return docgen.generate(cli.main)


def test_every_visible_command_has_a_page_and_hidden_ones_do_not():
    pages = _pages()
    for name, command in cli.main.commands.items():
        if command.hidden:
            assert f"{name}.md" not in pages, name
        else:
            assert f"{name}.md" in pages, name
    assert "upload-data.md" not in pages
    assert "docs.md" not in pages


def test_pages_carry_the_frontmatter_the_site_expects():
    page = _pages()["start.md"]
    head = page.split("---")[1]
    for line in (
        'title: "arcsecond start"',
        "visibility: public",
        "audience: operator",
        "tier: reference",
        "source: generated",
        f'cli: "{__version__.__version__}"',
    ):
        assert line in head, line
    assert "audience: astronomer" in _pages()["upload.md"]


def test_a_page_shows_usage_help_arguments_and_options():
    page = _pages()["restart.md"]
    assert "```\narcsecond restart [OPTIONS] [SERVICES]...\n```" in page
    assert "editing .env" in page
    assert "- `[SERVICES]...` — optional" in page
    assert "| `--dir FOLDER` |" in page
    assert "| `-v, --verbose` |" in page


def test_hidden_options_stay_out():
    page = _pages()["proxy.md"]
    assert "--no-banner" not in page
    assert "--no-autostart" in page


def test_no_rewrap_paragraphs_become_code_fences():
    page = _pages()["api.md"]
    assert "```\narcsecond api                          list the servers" in page
    # ...and their contents are not HTML-escaped inside the fence.
    assert "&lt;" not in page.split("```")[3]


def test_groups_list_and_render_their_subcommands():
    page = _pages()["api.md"]
    assert "**Subcommands**" in page
    assert "[`arcsecond api use`](#arcsecond-api-use)" in page
    assert "## `arcsecond api use`" in page
    assert "arcsecond api use [OPTIONS] NAME" in page
    # Three levels deep.
    alpaca = _pages()["alpaca.md"]
    assert "### `arcsecond alpaca probe dome`" in alpaca


def test_prose_is_escaped_for_vitepress():
    for name, page in _pages().items():
        if not name.endswith(".md"):
            continue
        body = page.split("---", 2)[2]
        outside_code = "\n".join(
            line
            for line in body.splitlines()
            if not line.startswith("```") and "`" not in line
        )
        assert "<" not in outside_code, name
        assert "{{" not in outside_code, name


def test_the_index_and_manifest_cover_the_same_commands():
    pages = _pages()
    manifest = json.loads(pages[docgen.MANIFEST_FILENAME])
    names = [entry["name"] for entry in manifest["commands"]]
    assert names == sorted(n for n, c in cli.main.commands.items() if not c.hidden)
    assert manifest["version"] == __version__.__version__
    index = pages[docgen.INDEX_FILENAME]
    for name in names:
        assert f"[`arcsecond {name}`](./{name}.md)" in index


def test_the_command_writes_and_then_verifies_its_own_output(tmp_path):
    out = tmp_path / "commands"
    result = CliRunner().invoke(cli.main, ["docs", "commands", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert (out / "start.md").exists() and (out / "index.md").exists()

    check = CliRunner().invoke(cli.main, ["docs", "commands", "--check", str(out)])
    assert check.exit_code == 0, check.output
    assert "up to date" in check.output

    (out / "start.md").write_text("edited by hand\n")
    (out / "gone.md").write_text("a command that no longer exists\n")
    check = CliRunner().invoke(cli.main, ["docs", "commands", "--check", str(out)])
    assert check.exit_code == 1
    assert "start.md" in check.output
    assert "gone.md (stale)" in check.output


def test_without_out_or_check_it_says_what_it_needs():
    result = CliRunner().invoke(cli.main, ["docs", "commands"])
    assert result.exit_code != 0
    assert "--out" in result.output


def test_docs_is_hidden_from_operators():
    assert cli.main.commands["docs"].hidden
    assert (
        "docs"
        not in CliRunner().invoke(cli.main, ["--help"]).output.split("Commands:")[1]
    )


def test_help_is_dedented_whatever_python_left_in_the_docstring():
    """Python 3.12 keeps a docstring's indentation, 3.13 strips it; the page
    must not depend on which one generated it."""
    raw = (
        "First line.\n\n    A second paragraph, indented as 3.12\n    leaves it.\n\n"
        "    \b\n      example one\n      example two\n"
    )
    rendered = "\n".join(docgen._render_help(raw))
    assert "\n    A second" not in rendered
    assert "A second paragraph, indented as 3.12\nleaves it." in rendered
    assert "```\nexample one\nexample two\n```" in rendered
