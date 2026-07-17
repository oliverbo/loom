from __future__ import annotations

from loom.site.deploy.delta import compute_delta
from loom.site.deploy.manifest import DeploymentManifest, FileEntry, SourceInfo


def _manifest(files: dict[str, str]) -> DeploymentManifest:
    return DeploymentManifest(
        version=1,
        source=SourceInfo(commit="abc", dirty=False),
        files={path: FileEntry(sha256=sha) for path, sha in files.items()},
    )


def test_first_deployment_treats_everything_as_added() -> None:
    new = _manifest({"index.html": "h1", "feed.xml": "h2"})

    delta = compute_delta(None, new)

    assert delta.added == ("feed.xml", "index.html")
    assert delta.modified == ()
    assert delta.deleted == ()
    assert delta.unchanged == ()


def test_classifies_added_modified_deleted_unchanged() -> None:
    previous = _manifest(
        {
            "index.html": "h1",
            "feed.xml": "h2",
            "posts/removed/index.html": "h3",
        }
    )
    new = _manifest(
        {
            "index.html": "h1",  # unchanged
            "feed.xml": "h2-new",  # modified
            "posts/new-post/index.html": "h4",  # added
        }
    )

    delta = compute_delta(previous, new)

    assert delta.added == ("posts/new-post/index.html",)
    assert delta.modified == ("feed.xml",)
    assert delta.deleted == ("posts/removed/index.html",)
    assert delta.unchanged == ("index.html",)


def test_identical_manifests_produce_no_changes() -> None:
    manifest = _manifest({"index.html": "h1", "feed.xml": "h2"})

    delta = compute_delta(manifest, manifest)

    assert delta.added == ()
    assert delta.modified == ()
    assert delta.deleted == ()
    assert delta.unchanged == ("feed.xml", "index.html")


def test_results_are_sorted() -> None:
    previous = _manifest({"z.html": "h1", "a.html": "h2"})
    new = _manifest({"z.html": "h1-new", "b.html": "h3"})

    delta = compute_delta(previous, new)

    assert delta.modified == ("z.html",)
    assert delta.added == ("b.html",)
    assert delta.deleted == ("a.html",)
