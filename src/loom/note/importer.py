"""`loom note import`: bring an existing post (file or directory) into a
`loom site`'s posts directory, backfilling required front matter.

Unlike `loom note add`, importing always targets a site -- there's no
plain "notes repository" mode -- since the whole point is migrating
existing posts into a site's mandatory front matter schema.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import datetime
from pathlib import Path
from typing import Any

from writer_md import split_front_matter
from writer_md.errors import WriterMdError

from loom.errors import ContentError, NoteError
from loom.note.scaffold import render_front_matter
from loom.site.config import load_config
from loom.site.content.discovery import _resolve_post_directory
from loom.site.content.frontmatter import KNOWN_KEYS
from loom.site.validation import validate_site
from loom.slug import slugify, titleize

_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[-_](.+))?$")
# Tried, in order, against a front matter `date`/`published` string that
# isn't already a bare ISO date (which `date.fromisoformat` handles on
# its own) -- common alternate formats seen in other tools' exports.
_DATE_FORMATS = (
    "%m/%d/%Y",  # 7/20/2026 (US)
    "%m-%d-%Y",  # 7-20-2026
    "%Y/%m/%d",  # 2026/07/20
    "%B %d, %Y",  # July 20, 2026
    "%B %d %Y",  # July 20 2026
    "%d %B %Y",  # 20 July 2026
    "%b %d, %Y",  # Jul 20, 2026
    "%b %d %Y",  # Jul 20 2026
)
_CANONICAL_BY_LOWER = {key.lower(): key for key in KNOWN_KEYS}
# Alternate spellings for a canonical field, beyond mere case, as seen in
# other tools' front matter (e.g. Jekyll's `published`/`Published`).
_ALIASES_BY_LOWER = {"published": "date"}


@dataclass(frozen=True)
class ImportNoteResult:
    """The outcome of `import_note`. `validation_errors` mirrors
    `AddNoteResult.validation_errors` -- the note is imported either way;
    only the caller's exit code should depend on whether it's empty.
    """

    path: Path
    validation_errors: list[str] = field(default_factory=list)


def import_note(root: Path, source: Path, *, today: str) -> ImportNoteResult:
    """Import `source` (a `.md` file or a post-bundle directory) into the
    `loom site` at `root`.

    `root` must be a `loom site` (i.e. contain `.loom/loom.toml`); the
    note is written into that site's configured posts directory
    (`posts_dir` in `loom.toml`). Missing `title`, `slug`, `date`,
    `draft`, `tags` front matter is backfilled, and case-differing keys
    (e.g. `Title`) are folded to the spelling Loom requires, and a
    `published`/`Published` field is recognized as an alias for `date`.
    `today` is
    accepted for parity with `add_note` but is only ever used if a
    `source` somehow has neither existing front matter, a dated name, nor
    a readable modification time.

    A leading `YYYY-MM-DD` in `source`'s file/directory name both
    supplies the published date (when front matter doesn't already have
    one) and is stripped from the name used for the destination and for
    deriving `title`/`slug` -- e.g. `2024-01-15-hello-world.md` becomes
    `content/posts/hello-world.md`.
    """
    config = load_config(root)
    posts_base = config.resolve(config.posts_dir)

    main_file, bundle_dir, raw_name = _resolve_source(source)
    date_from_name, dest_stem = _split_date_prefix(raw_name)

    if bundle_dir is not None:
        # The bundle directory is renamed (date prefix stripped, if any),
        # and the main file is renamed to match it -- even though a
        # directory with only one `.md` file accepts any name for it
        # (see `_resolve_post_directory`), leaving it as-is could make
        # the bundle ambiguous to a *later* `loom site build`/`validate`
        # if a sibling `.md` file is ever added, since they apply the
        # exact same "matches the directory name" rule to pick it back
        # out. Normalizing it now avoids that trap.
        destination_dir = posts_base / dest_stem
        destination = destination_dir / f"{dest_stem}.md"
        if destination_dir.exists():
            raise NoteError(f"{destination_dir} already exists")

        # `copytree` creates `destination_dir` (and any missing parents,
        # e.g. `posts_base` itself) since it must not already exist.
        shutil.copytree(bundle_dir, destination_dir)
        copied_main = destination_dir / main_file.name
        if copied_main != destination:
            copied_main.rename(destination)
        text = destination.read_text(encoding="utf-8")
    else:
        destination = posts_base / f"{dest_stem}.md"
        if destination.exists():
            raise NoteError(f"{destination} already exists")

        destination.parent.mkdir(parents=True, exist_ok=True)
        text = main_file.read_text(encoding="utf-8")

    try:
        raw_front_matter, body = split_front_matter(text, source=main_file, required=False)
    except WriterMdError as exc:
        raise ContentError(str(exc)) from exc

    front_matter = _normalize_keys(raw_front_matter)
    changed = front_matter.keys() != raw_front_matter.keys()

    resolved_date = _resolve_date(
        front_matter, date_from_name=date_from_name, mtime_source=source, today=today
    )

    before = dict(front_matter)
    _fill_defaults(front_matter, name=dest_stem, resolved_date=resolved_date)
    changed = changed or front_matter != before

    if changed:
        destination.write_text(render_front_matter(front_matter, body), encoding="utf-8")
    elif bundle_dir is None:
        # For a bundle, `copytree` already physically placed the
        # untouched file at `destination`. A plain file import has no
        # such prior copy step, so write the original text verbatim.
        destination.write_text(text, encoding="utf-8")

    validation_errors = validate_site(root)
    return ImportNoteResult(path=destination, validation_errors=validation_errors)


def _resolve_source(source: Path) -> tuple[Path, Path | None, str]:
    """Return `(main_file, bundle_dir, raw_name)` for `source`.

    `bundle_dir` is `None` for a plain file import; otherwise it's
    `source` itself, copied wholesale (see `import_note`). `raw_name` is
    `source.stem` (file) or `source.name` (directory), not yet stripped
    of a date prefix.
    """
    if not source.exists():
        raise NoteError(f"{source} does not exist")

    if source.is_file():
        if source.suffix != ".md":
            raise NoteError(f"{source}: not a Markdown file")
        return source, None, source.stem

    if source.is_dir():
        try:
            resolved = _resolve_post_directory(source)
        except ContentError as exc:
            raise NoteError(str(exc)) from exc
        return resolved.md_path, source, source.name

    raise NoteError(f"{source}: not a file or directory")


def _split_date_prefix(name: str) -> tuple[str | None, str]:
    """Split a leading `YYYY-MM-DD` off `name`, if it's a valid date.

    Returns `(iso_date, remainder)` when `name` starts with a valid date
    (`remainder` is whatever follows a `-`/`_` separator, or `name`
    itself unchanged if the date isn't followed by anything to strip --
    stripping it would leave an empty name). Returns `(None, name)`
    unchanged if there's no leading date, or the digits present don't
    form a real calendar date.
    """
    match = _DATE_PREFIX.match(name)
    if not match:
        return None, name

    date_text, remainder = match.group(1), match.group(2)
    try:
        date_cls.fromisoformat(date_text)
    except ValueError:
        return None, name

    return date_text, (remainder or name)


def _normalize_keys(raw: dict[str, Any]) -> dict[str, Any]:
    """Fold case-differing and aliased front matter keys to Loom's
    canonical spelling.

    A key that matches one of `KNOWN_KEYS` case-insensitively (e.g.
    `Title`, `DATE`) is rewritten to its canonical (lowercase) form. A
    key matching `_ALIASES_BY_LOWER` (currently just `published`/
    `Published`, for `date`) is folded the same way, but only if the
    canonical field isn't *also* present under its own name -- an
    explicit `date` always wins over a `published` alias rather than
    being silently overwritten by it. Any other key is preserved
    untouched, including its original casing -- same as `Document.extra`'s
    treatment of unrecognized front matter.
    """
    normalized: dict[str, Any] = {}
    aliased: dict[str, Any] = {}
    for key, value in raw.items():
        lowered = key.strip().lower()
        canonical = _CANONICAL_BY_LOWER.get(lowered)
        if canonical:
            normalized[canonical] = value
            continue
        alias_target = _ALIASES_BY_LOWER.get(lowered)
        if alias_target:
            aliased.setdefault(alias_target, value)
        else:
            normalized[key] = value
    for canonical, value in aliased.items():
        normalized.setdefault(canonical, value)
    return normalized


def _resolve_date(
    front_matter: dict[str, Any], *, date_from_name: str | None, mtime_source: Path, today: str
) -> str:
    """Resolve the published date: existing front matter `date` ->
    `date_from_name` (from a filename/dirname prefix, if any) ->
    `mtime_source`'s last-modified time -> `today`, as an
    unreachable-in-practice final fallback.

    An existing `date` that can't be parsed in any recognized format is
    treated the same as a missing one (falls through to the rest of the
    chain) rather than aborting the whole import over one bad field.
    """
    existing = front_matter.get("date")
    if existing:
        coerced = _try_coerce_date(existing)
        if coerced is not None:
            return coerced

    if date_from_name is not None:
        return date_from_name

    try:
        mtime = mtime_source.stat().st_mtime
    except OSError:
        return today
    return date_cls.fromtimestamp(mtime).isoformat()


def _try_coerce_date(value: Any) -> str | None:
    """Coerce a front matter `date`/`published` value to an ISO string.

    Accepts a YAML-native `date`/`datetime` (e.g. an unquoted `2024-01-15`
    front matter value, which PyYAML parses as a `date` on its own), a
    bare ISO string, or one of `_DATE_FORMATS`'s common alternate
    spellings (e.g. `7/20/2026`). Returns `None`, rather than raising, if
    `value` doesn't match any of them.
    """
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date_cls):
        return value.isoformat()

    text = str(value).strip()
    try:
        return date_cls.fromisoformat(text).isoformat()
    except ValueError:
        pass

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    return None


def _fill_defaults(front_matter: dict[str, Any], *, name: str, resolved_date: str) -> None:
    """Fill missing/blank `title` and `slug`; set `date`; default `draft`
    and `tags`.

    Order matters: `title` must be resolved before `slug` is derived from
    it, same as `scaffold._fill_site_defaults`. Unlike `title`/`slug`,
    `date` is always (re)written to `resolved_date` rather than only when
    missing -- `resolved_date` already encodes "keep the existing date if
    it parsed, otherwise fall back" (see `_resolve_date`), and a
    non-ISO-but-parseable existing value (e.g. `7/20/2026`) still needs
    to be normalized to the ISO string Loom's own front matter schema
    requires.
    """
    if not front_matter.get("title"):
        front_matter["title"] = titleize(name)
    if not front_matter.get("slug"):
        front_matter["slug"] = slugify(str(front_matter["title"]))
    front_matter["date"] = resolved_date
    front_matter.setdefault("draft", False)
    front_matter.setdefault("tags", [])
