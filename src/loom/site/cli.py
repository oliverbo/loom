"""The `loom site` command group: init, build, preview, and deploy a static site."""

from __future__ import annotations

import http.server
import socketserver
from datetime import date
from pathlib import Path

import typer

from loom.errors import DeployError, LoomError, ManifestError, ValidationError
from loom.site.build.pipeline import build_site
from loom.site.config import load_config
from loom.site.deploy import INCREMENTAL_BACKENDS, TARGETS
from loom.site.deploy.manifest import MANIFEST_FILENAME, read_manifest
from loom.site.deploy.pipeline import DeploymentResult, run_deployment
from loom.site.scaffold import init_site
from loom.site.validation import validate_site

app = typer.Typer(help="Manage a Loom site: init, build, preview, and deploy.")

PathArg = typer.Argument(Path("."), help="Path to the site (defaults to the current directory).")


@app.command()
def init(path: Path = PathArg) -> None:
    """Scaffold a new site at PATH."""
    path.mkdir(parents=True, exist_ok=True)
    try:
        init_site(path, today=date.today().isoformat())
    except LoomError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"Initialized a new Loom site at {path}", fg=typer.colors.GREEN)


@app.command()
def validate(path: Path = PathArg) -> None:
    """Validate content and configuration at PATH."""
    errors = validate_site(path)
    if errors:
        for error in errors:
            typer.secho(f"error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    typer.secho("Site is valid.", fg=typer.colors.GREEN)


@app.command()
def build(
    path: Path = PathArg,
    drafts: bool = typer.Option(False, "--drafts", help="Include draft posts."),
) -> None:
    """Build the site at PATH into its output directory."""
    try:
        output_dir = build_site(path, include_drafts=drafts)
    except ValidationError as exc:
        for error in exc.errors:
            typer.secho(f"error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"Built site into {output_dir}", fg=typer.colors.GREEN)


@app.command()
def preview(
    path: Path = PathArg,
    port: int = typer.Option(8000, "--port", help="Port to serve on."),
) -> None:
    """Serve the site's build output locally."""
    config = load_config(path)
    output_dir = config.resolve(config.output_dir)
    if not output_dir.is_dir():
        typer.secho(
            f"No build output at {output_dir}; run `loom site build` first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    handler = _static_handler_for(output_dir)
    with socketserver.TCPServer(("", port), handler) as httpd:
        typer.echo(f"Serving {output_dir} at http://localhost:{port}/ (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def _static_handler_for(directory: Path) -> type[http.server.SimpleHTTPRequestHandler]:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

    return Handler


@app.command()
def deploy(
    path: Path = PathArg,
    no_build: bool = typer.Option(False, "--no-build", help="Skip rebuilding before deploy."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be deployed without uploading, deleting, or saving a manifest.",
    ),
    allow_dirty: bool = typer.Option(
        False, "--allow-dirty", help="Allow deploying with an uncommitted Git working tree."
    ),
) -> None:
    """Build (unless --no-build) and deploy the site at PATH."""
    config = load_config(path)

    target_name = config.deploy.target
    if not target_name:
        typer.secho("No [deploy] target configured in loom.toml.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    if target_name not in TARGETS and target_name not in INCREMENTAL_BACKENDS:
        typer.secho(f"Unknown deploy target: {target_name!r}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if no_build:
        output_dir = config.resolve(config.output_dir)
        if not output_dir.is_dir():
            typer.secho(
                f"No build output at {output_dir}; run `loom site build` first.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
    else:
        typer.echo("Building site...")
        try:
            output_dir = build_site(path)
        except ValidationError as exc:
            for error in exc.errors:
                typer.secho(f"error: {error}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc

    try:
        new_manifest = read_manifest(output_dir / MANIFEST_FILENAME)
    except ManifestError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if new_manifest is None:
        typer.secho(
            f"No deployment manifest found in {output_dir}; run `loom site build`.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    typer.echo(f"Generated {len(new_manifest.files)} files.\n")

    if new_manifest.source.dirty and not allow_dirty and not dry_run:
        typer.secho(
            "Working tree is dirty; commit your changes or pass --allow-dirty.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    if target_name in INCREMENTAL_BACKENDS:
        backend = INCREMENTAL_BACKENDS[target_name](config.deploy, path)
        try:
            result = run_deployment(output_dir, backend, new_manifest, dry_run=dry_run)
        except DeployError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
        _print_deployment_summary(result)
        return

    if dry_run:
        typer.echo(
            f"Dry run: would deploy {output_dir} via {target_name} "
            "(no incremental preview available for this target)."
        )
        return

    target = TARGETS[target_name](config.deploy)
    try:
        target.deploy(output_dir)
    except DeployError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"Deployed {output_dir} via {target_name}.", fg=typer.colors.GREEN)
    if new_manifest.source.commit:
        typer.echo(f"Source commit: {new_manifest.source.commit}")


def _print_deployment_summary(result: DeploymentResult) -> None:
    delta = result.delta
    typer.echo("Deployment changes:")
    typer.echo(f"  {len(delta.added)} added")
    typer.echo(f"  {len(delta.modified)} modified")
    typer.echo(f"  {len(delta.deleted)} deleted")
    typer.echo(f"  {len(delta.unchanged)} unchanged")

    uploading = (*delta.added, *delta.modified)
    if uploading:
        typer.echo("\nUploading:")
        for relative_path in uploading:
            typer.echo(f"  {relative_path}")

    if delta.deleted:
        typer.echo("\nDeleting:")
        for relative_path in delta.deleted:
            typer.echo(f"  {relative_path}")

    typer.echo()
    if result.dry_run:
        typer.secho("Dry run: no changes made.", fg=typer.colors.YELLOW)
    else:
        typer.secho("Deployment complete.", fg=typer.colors.GREEN)
    if result.commit:
        typer.echo(f"Source commit: {result.commit}")
