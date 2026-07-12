"""The `loom` command-line interface.

Loom groups its functionality by area. Today that's `site` (static-site
publishing); more groups can be registered here as Loom grows into a more
general tool for file-system-based content repositories.
"""

from __future__ import annotations

import typer

from loom.site.cli import app as site_app

app = typer.Typer(help="Loom: a toolkit for file-system-based content repositories.")
app.add_typer(site_app, name="site", help="Manage a Loom site: init, build, preview, and deploy.")

if __name__ == "__main__":
    app()
