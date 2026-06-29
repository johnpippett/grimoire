"""Project discovery and configuration for wiki-rag-mcp.

Discovers project wiki folders under a configurable root directory (set via
``WIKI_RAG_PROJECTS_ROOT`` env var, default ``~/projects``). Each
subdirectory of the root is treated as a project. A project's wiki sources
default to its ``wiki/`` subdirectory; if a ``Project Vault/``,
``project-vault/``, or ``ProjectVault/`` subdirectory is present it is also
indexed. Users can override the discovery with a JSON file at
``$WIKI_RAG_HOME/projects.json``.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

DEFAULT_PROJECTS_ROOT = Path("~/projects").expanduser()
DEFAULT_WIKI_DIR_NAMES = ("wiki",)
DEFAULT_VAULT_DIR_NAMES = ("Project Vault", "project-vault", "ProjectVault")

# File extensions we treat as wiki content.
WIKI_FILE_EXTENSIONS = {".md", ".markdown", ".mdx", ".txt"}

# Names of hidden / generated dirs we never want to walk into.
SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".DS_Store",
    "indexes",  # our own persisted indexes
    "logs",
    ".playwright-cli",
    ".aider-router",
    ".aider.tags.cache.v4",
    ".commandcode",
    ".pi-lens",
    ".opencode",
    ".wrangler",
    ".agent",
    ".github",
}


@dataclass
class Project:
    """A single project with one or more wiki source roots."""

    name: str
    root: Path
    wiki_roots: list[Path] = field(default_factory=list)
    description: str = ""

    @property
    def slug(self) -> str:
        return _slugify(self.name)

    def index_path(self, home: Path) -> Path:
        return home / "indexes" / self.slug

    def has_any_sources(self) -> bool:
        return any(p.exists() and p.is_dir() for p in self.wiki_roots)

    def list_source_files(self) -> list[Path]:
        files: list[Path] = []
        for root in self.wiki_roots:
            if not root.exists() or not root.is_dir():
                continue
            for path in _walk_text_files(root):
                files.append(path)
        # Stable order — makes diffs predictable.
        files.sort()
        return files

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "root": str(self.root),
            "wiki_roots": [str(p) for p in self.wiki_roots],
            "description": self.description,
        }


@dataclass
class Registry:
    """Collection of discovered projects and runtime paths."""

    projects_root: Path
    home: Path
    projects: list[Project]

    def get(self, name_or_slug: str) -> Project | None:
        needle = name_or_slug.strip()
        for project in self.projects:
            if project.name == needle or project.slug == needle:
                return project
        return None

    def names(self) -> list[str]:
        return [p.name for p in self.projects]


def _slugify(name: str) -> str:
    safe = []
    for ch in name.lower():
        if ch.isalnum():
            safe.append(ch)
        elif ch in {" ", "_", "-", "."}:
            safe.append("-")
    slug = "".join(safe).strip("-")
    return slug or "project"


def _walk_text_files(root: Path) -> Iterable[Path]:
    """Yield text files under ``root`` skipping generated dirs."""
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter dirnames in-place so os.walk doesn't descend.
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES and not d.startswith(".")]
        for fname in filenames:
            if fname.startswith("."):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in WIKI_FILE_EXTENSIONS:
                yield Path(dirpath) / fname


def _read_overrides(home: Path) -> dict:
    """Read user-provided project overrides from ``projects.json``."""
    path = home / "projects.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to parse %s: %s", path, exc)
        return {}


def _discover_wiki_roots(project_root: Path) -> list[Path]:
    """Return the default wiki roots for a project (no overrides)."""
    roots: list[Path] = []
    for name in DEFAULT_WIKI_DIR_NAMES:
        candidate = project_root / name
        if candidate.is_dir():
            roots.append(candidate)
    for name in DEFAULT_VAULT_DIR_NAMES:
        candidate = project_root / name
        if candidate.is_dir() and candidate not in roots:
            roots.append(candidate)
    return roots


def discover_projects(projects_root: Path, home: Path) -> list[Project]:
    """Scan ``projects_root`` and return the discovered projects.

    Honors per-project overrides in ``$home/projects.json``::

        {
          "include": ["Project A", "Project B"],
          "exclude": ["Archived Project"],
          "overrides": {
            "My Project": {
              "wiki_roots": ["/abs/path/to/wiki", "/abs/path/to/notes"]
            }
          }
        }
    """
    if not projects_root.is_dir():
        raise FileNotFoundError(f"Projects root not found: {projects_root}")

    overrides = _read_overrides(home)
    include = set(overrides.get("include") or [])
    exclude = set(overrides.get("exclude") or [])
    project_overrides = overrides.get("overrides") or {}

    discovered: list[Project] = []
    for child in sorted(projects_root.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue
        if child.name in SKIP_DIR_NAMES:
            continue
        if exclude and child.name in exclude:
            continue
        if include and child.name not in include:
            continue

        override = project_overrides.get(child.name, {}) or {}
        custom_roots = override.get("wiki_roots")
        if custom_roots:
            wiki_roots = [Path(p).expanduser() for p in custom_roots]
        else:
            wiki_roots = _discover_wiki_roots(child)

        project = Project(
            name=child.name,
            root=child,
            wiki_roots=wiki_roots,
            description=override.get("description", ""),
        )
        discovered.append(project)

    return discovered


def load_registry(
    projects_root: Path | None = None,
    home: Path | None = None,
) -> Registry:
    """Load the project registry, creating the home directory if needed."""
    root = projects_root or Path(
        os.environ.get("WIKI_RAG_PROJECTS_ROOT", str(DEFAULT_PROJECTS_ROOT))
    ).expanduser()
    base_home = home or Path(
        os.environ.get("WIKI_RAG_HOME", str(Path.home() / ".wiki-rag"))
    ).expanduser()
    base_home.mkdir(parents=True, exist_ok=True)
    (base_home / "indexes").mkdir(parents=True, exist_ok=True)
    projects = discover_projects(root, base_home)
    return Registry(projects_root=root, home=base_home, projects=projects)
