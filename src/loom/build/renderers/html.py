"""Renders post pages and the home page as HTML via Jinja2 templates."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from loom.config import SiteConfig
from loom.content.markdown import render_markdown
from loom.models import Document, Site
from loom.resources import DEFAULT_THEME_DIR


def _make_environment(site: Site) -> Environment:
    """Templates are looked up in the site's own `templates/` first, then
    fall back to Loom's bundled default theme -- a site only needs to
    override the templates it wants to customize.
    """
    site_templates = site.config.resolve(site.config.templates_dir)
    loader = FileSystemLoader([str(site_templates), str(DEFAULT_THEME_DIR)])
    return Environment(loader=loader, autoescape=select_autoescape(["html", "xml"]))


class HtmlRenderer:
    def render(self, site: Site, output_dir: Path) -> None:
        env = _make_environment(site)
        post_template = env.get_template("post.html.j2")
        index_template = env.get_template("index.html.j2")

        posts = site.sorted_documents()

        for doc in posts:
            post_dir = output_dir / doc.slug
            post_dir.mkdir(parents=True, exist_ok=True)
            html = post_template.render(
                site=site.config,
                post=doc,
                content=render_markdown(doc.body_markdown),
            )
            (post_dir / "index.html").write_text(html, encoding="utf-8")

        index_html = index_template.render(site=site.config, posts=posts)
        (output_dir / "index.html").write_text(index_html, encoding="utf-8")


def post_url(config: SiteConfig, doc: Document) -> str:
    """Absolute-path URL for a post, for use in templates and RSS."""
    base = config.base_url.rstrip("/")
    return f"{base}/{doc.slug}/"
