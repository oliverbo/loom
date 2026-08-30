"""The `loom note` command group: add notes from templates."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import typer

from loom.errors import LoomError, NoteError
from loom.note.scaffold import add_note

app = typer.Typer(help="Manage Loom notes: add notes from templates.")

PathArg = typer.Argument(Path("."), help="Path to the notes repository (defaults to the cwd).")


@app.command()
def add(
    name: str = typer.Argument(..., help="Base name for the new note, e.g. 'new-post'."),
    path: Path = PathArg,
    template: str = typer.Option(
        "default", "-t", "--template", help="Template name in .loom/templates."
    ),
    site: bool = typer.Option(
        False,
        "--site",
        help="Prepopulate front matter for a `loom site` post and validate the site afterward.",
    ),
    # `list[str]` annotation trips ruff's B008 mutable-default check even
    # though the actual default is `None`; typer requires this exact
    # signature shape for a repeatable option.
    field: list[str] | None = typer.Option(  # noqa: B008
        None, "-f", "--field", help="Set a front matter field as key=value (repeatable)."
    ),
) -> None:
    """Add a new note under PATH from a template."""
    try:
        fields = _parse_fields(field or [])
        result = add_note(
            path,
            name,
            template=template,
            fields=fields,
            site=site,
            today=date.today().isoformat(),
        )
    except LoomError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.secho(f"Created {result.path}", fg=typer.colors.GREEN)

    if result.validation_errors:
        for error in result.validation_errors:
            typer.secho(f"error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


def _parse_fields(raw_fields: list[str]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for raw in raw_fields:
        if "=" not in raw:
            raise NoteError(f"--field {raw!r} must be in the form key=value")
        key, value = raw.split("=", 1)
        fields[key] = _coerce_field(key, value)
    return fields


def _coerce_field(key: str, value: str) -> Any:
    if key == "tags":
        return [tag.strip() for tag in value.split(",")]
    if key == "draft":
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        raise NoteError(f"--field draft={value!r} must be 'true' or 'false'")
    return value
