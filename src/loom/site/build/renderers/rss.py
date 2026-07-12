"""Renders `feed.xml`, an RSS 2.0 feed of published posts."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from loom.site.build.renderers.html import post_url
from loom.site.models import Site
from loom.site.resources import DEFAULT_THEME_DIR

MAX_ITEMS = 20


def _rfc822(value: date) -> str:
    """RSS 2.0 requires RFC 822 dates; posts only carry a date (no time
    of day), so we anchor each item at midnight UTC.
    """
    as_datetime = datetime.combine(value, time.min, tzinfo=UTC)
    return as_datetime.strftime("%a, %d %b %Y %H:%M:%S %z")


class RssRenderer:
    def render(self, site: Site, output_dir: Path) -> None:
        env = Environment(
            loader=FileSystemLoader([str(DEFAULT_THEME_DIR)]),
            autoescape=select_autoescape(["xml"]),
        )
        env.filters["rfc822"] = _rfc822
        template = env.get_template("feed.xml.j2")
        posts = site.sorted_documents()[:MAX_ITEMS]
        urls = {doc.slug: post_url(site.config, doc) for doc in posts}

        xml = template.render(site=site.config, posts=posts, urls=urls)
        (output_dir / "feed.xml").write_text(xml, encoding="utf-8")
