"""Build immutable BM25 generations at refresh time and reuse them for queries.

index.json is the atomic publication pointer. A file lock coordinates writers
and cold readers across processes; warm readers can finish on an old generation.
Persisted data uses BM25's JSON/NumPy format, never executable pickle files.
"""
from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field
import fcntl
import hashlib
from importlib.metadata import version
import json
import logging
import math
import os
from pathlib import Path
import re
import shutil
import threading
import time
import uuid
from typing import Any

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.vector_stores.utils import metadata_dict_to_node

from .config import Project, Registry, SKIP_DIR_NAMES, WIKI_FILE_EXTENSIONS

logger = logging.getLogger(__name__)
_DOCS_FILENAME = "documents.jsonl"  # legacy v1 detection only
_META_FILENAME = "index.json"
_CHUNK_SIZE = 1024
_CHUNK_OVERLAP = 128
_INDEX_VERSION = 2
_CACHE_MAX_PROJECTS = 8
# Admission/eviction budget measures persisted bytes, not exact Python heap size.
_CACHE_MAX_BYTES = 64 * 1024 * 1024
_CACHE: OrderedDict[str, _CachedRetriever] = OrderedDict()
_CACHE_LOCK = threading.RLock()


@dataclass
class IndexStats:
    project: str
    files_indexed: int
    files_skipped: int
    chunks: int
    bytes_indexed: int
    duration_s: float
    skipped: list[dict[str, str]] = field(default_factory=list)
    unchanged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {**vars(self), "duration_s": round(self.duration_s, 3)}


@dataclass
class _CachedRetriever:
    generation: str
    retriever: BM25Retriever | None
    size: int
    indexed_at: int
    wiki_roots: list[str]
    lock: threading.Lock = field(default_factory=threading.Lock)


class StaleGenerationError(ValueError):
    """Raised when a passage reference no longer names the current index."""

    def __init__(self, requested: str, current: str | None):
        self.requested = requested
        self.current = current
        super().__init__(
            f"Generation {requested!r} is not current; query again with query_wiki."
        )


@contextmanager
def _project_lock(project: Project, home: Path, *, shared: bool = False):
    folder = project.index_path(home)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ".index.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
        try:
            yield folder
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            match = re.match(r"^#\s+(.+)$", stripped)
            return match.group(1).strip() if match else stripped[:120]
    return fallback


def _settings(project: Project) -> dict[str, Any]:
    return {
        "indexer_version": _INDEX_VERSION,
        "project": project.name,
        "root": str(project.root.resolve()),
        "wiki_roots": [str(path.resolve()) for path in project.wiki_roots],
        "chunk_size": _CHUNK_SIZE,
        "chunk_overlap": _CHUNK_OVERLAP,
        "sentence_boundaries": "punctuation-whitespace-v1",
        "extensions": sorted(WIKI_FILE_EXTENSIONS),
        "skip_dirs": sorted(SKIP_DIR_NAMES),
        "dependencies": {name: version(name) for name in
                         ("llama-index-core", "llama-index-retrievers-bm25", "bm25s")},
    }


def _snapshot(project: Project):
    """Hash actual bytes (including empty/unreadable files) and reuse them to build."""
    sources = []
    manifest = []
    skipped = []
    for path in sorted(set(project.list_source_files())):
        try:
            data = path.read_bytes()
        except OSError as exc:
            reason = f"read error: {exc}"
            skipped.append({"file": str(path), "reason": reason})
            manifest.append({"path": str(path), "error": reason})
            continue
        manifest.append({"path": str(path), "sha256": hashlib.sha256(data).hexdigest()})
        text = data.decode("utf-8", errors="replace")
        if not text.strip():
            skipped.append({"file": str(path), "reason": "empty"})
        else:
            sources.append((path, text))
    return sources, manifest, skipped


def _generation_path(folder: Path, meta: dict[str, Any] | None) -> Path | None:
    if not meta or meta.get("indexer_version") != _INDEX_VERSION:
        return None
    generation = meta.get("generation", "")
    if not isinstance(generation, str) or not re.fullmatch(r"[0-9a-f]{32}", generation):
        return None
    path = folder / "generations" / generation
    return path if path.is_dir() else None


def _stats(project: Project, meta: dict[str, Any], start: float, unchanged=False):
    return IndexStats(project.name, meta["files_indexed"], meta["files_skipped"],
                      meta["chunks"], meta["bytes_indexed"], time.perf_counter() - start,
                      meta.get("skipped", []), unchanged)


def index_project(project: Project, home: Path, force: bool = False) -> IndexStats:
    """Publish a prepared generation, or skip unchanged source bytes and settings."""
    start = time.perf_counter()
    with _project_lock(project, home) as folder:
        sources, manifest, skipped = _snapshot(project)
        settings = _settings(project)
        old = read_meta(project, home)
        old_target = _generation_path(folder, old)
        try:
            previous = json.loads((old_target / "manifest.json").read_text(encoding="utf-8")) if old_target else {}
        except (OSError, ValueError):
            previous = {}
        if (not force and _generation_path(folder, old) is not None
                and previous.get("manifest") == manifest and previous.get("settings") == settings
                and not any("error" in item for item in manifest)):
            return _stats(project, {**old, "skipped": previous.get("skipped", [])}, start, unchanged=True)
        docs = []
        for path, text in sources:
            rel = str(path.relative_to(project.root)) if path.is_relative_to(project.root) else str(path)
            docs.append(Document(
                id_=hashlib.sha256(str(path).encode()).hexdigest(), text=text,
                metadata={"project": project.name, "file_path": str(path),
                          "rel_path": rel, "title": _extract_title(text, path.stem)},
                excluded_llm_metadata_keys=["file_path"],
                excluded_embed_metadata_keys=["file_path"],
            ))
        splitter = SentenceSplitter(
            chunk_size=_CHUNK_SIZE, chunk_overlap=_CHUNK_OVERLAP,
            # Keep all text while avoiding NLTK's runtime imports/downloads.
            # Paragraph, token-budget and long-sentence fallback splitting remain
            # managed by SentenceSplitter; this is a simple boundary heuristic.
            chunking_tokenizer_fn=lambda text: re.split(r"(?<=[.!?])(?=\s)", text),
            id_func=lambda i, doc: hashlib.sha256(f"{doc.id_}:{i}".encode()).hexdigest(),
        )
        nodes = splitter.get_nodes_from_documents(docs) if docs else []
        generation = uuid.uuid4().hex
        target = folder / "generations" / generation
        target.mkdir(parents=True)
        pointer = folder / f".index-{generation}.json"
        try:
            if nodes:
                retriever = BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=min(5, len(nodes)))
                retriever.persist(str(target))
            (target / "manifest.json").write_text(
                json.dumps({"manifest": manifest, "settings": settings, "skipped": skipped}, ensure_ascii=False),
                encoding="utf-8",
            )
            size = sum(path.stat().st_size for path in target.iterdir() if path.is_file())
            meta = {
                "project": project.name, "slug": project.slug,
                "wiki_roots": [str(path) for path in project.wiki_roots],
                "files_indexed": len(docs), "files_skipped": len(skipped),
                "source_file_count": len(manifest),
                "chunks": len(nodes), "bytes_indexed": sum(len(text.encode("utf-8")) for _, text in sources),
                "indexed_at": int(time.time()), "indexer_version": _INDEX_VERSION,
                "generation": generation,
                "persisted_bytes": size,
            }
            with pointer.open("w", encoding="utf-8") as stream:
                json.dump(meta, stream, indent=2, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pointer, folder / _META_FILENAME)
        except BaseException:
            shutil.rmtree(target, ignore_errors=True)
            pointer.unlink(missing_ok=True)
            raise
        # Cold readers hold a shared lock through loading; cached readers own all
        # their data in memory. Thus old generations can be removed without races.
        for path in target.parent.iterdir():
            if path != target and path.is_dir() and re.fullmatch(r"[0-9a-f]{32}", path.name):
                shutil.rmtree(path, ignore_errors=True)
        with _CACHE_LOCK:
            _CACHE.pop(str(folder.resolve()), None)
        logger.info("indexed %s: %d files, %d chunks", project.name, len(docs), len(nodes))
        return _stats(project, {**meta, "skipped": skipped}, start)


def _cached_retriever(project: Project, home: Path) -> _CachedRetriever:
    folder = project.index_path(home)
    key = str(folder.resolve())
    meta = read_meta(project, home)
    if _generation_path(folder, meta) is None:
        if not has_index(project, home):
            raise FileNotFoundError(f"No index for {project.name!r}. Run reindex_project first.")
        # v1 indexes contained raw documents. Rebuild once from current sources.
        index_project(project, home)
        meta = read_meta(project, home)
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached is not None and cached.generation == meta["generation"]:
            _CACHE.move_to_end(key)
            return cached
    # Do not hold the global cache mutex while waiting for an index writer.
    with _project_lock(project, home, shared=True):
        meta = read_meta(project, home)
        target = _generation_path(folder, meta)
        if target is None:
            raise FileNotFoundError(f"Index for {project.name!r} disappeared; reindex it.")
        with _CACHE_LOCK:
            cached = _CACHE.get(key)
            if cached is not None and cached.generation == meta["generation"]:
                _CACHE.move_to_end(key)
                return cached
        retriever = BM25Retriever.from_persist_dir(str(target)) if meta["chunks"] else None
        cached = _CachedRetriever(
            meta["generation"], retriever, meta["persisted_bytes"],
            meta.get("indexed_at", 0), list(meta.get("wiki_roots", [])),
        )
        with _CACHE_LOCK:
            # Another cold reader may have completed while this one was loading.
            existing = _CACHE.get(key)
            if existing is not None and existing.generation == cached.generation:
                _CACHE.move_to_end(key)
                return existing
            _CACHE.pop(key, None)
            if cached.size <= _CACHE_MAX_BYTES:
                _CACHE[key] = cached
                while (len(_CACHE) > _CACHE_MAX_PROJECTS
                       or sum(entry.size for entry in _CACHE.values()) > _CACHE_MAX_BYTES):
                    _CACHE.popitem(last=False)
            return cached


@dataclass
class Hit:
    score: float
    text: str
    file_path: str
    rel_path: str
    title: str
    project: str
    chunk_id: str
    generation: str
    indexed_at: int
    wiki_roots: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "text": self.text,
            "file_path": self.file_path,
            "rel_path": self.rel_path,
            "title": self.title,
            "project": self.project,
            "chunk_id": self.chunk_id,
            "generation": self.generation,
            "indexed_at": self.indexed_at,
            "wiki_roots": self.wiki_roots,
        }


class QueryHits(list[Hit]):
    """A list of hits with the generation that produced the query result."""

    def __init__(
        self,
        hits: list[Hit],
        *,
        generation: str,
        indexed_at: int,
        wiki_roots: list[str],
    ):
        super().__init__(hits)
        self.generation = generation
        self.indexed_at = indexed_at
        self.wiki_roots = list(wiki_roots)

    def index_meta(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "indexed_at": self.indexed_at,
            "wiki_roots": self.wiki_roots,
        }


def query_project(project: Project, home: Path, question: str, top_k: int = 5) -> list[Hit]:
    """Query a prepared generation; per-retriever locking isolates top-k settings."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 25:
        raise ValueError("top_k must be an integer between 1 and 25")
    cached = _cached_retriever(project, home)
    if cached.retriever is None:
        return QueryHits(
            [], generation=cached.generation, indexed_at=cached.indexed_at,
            wiki_roots=cached.wiki_roots,
        )
    with cached.lock:
        cached.retriever.similarity_top_k = min(top_k, len(cached.retriever.corpus))
        results = cached.retriever.retrieve(question)
    hits = []
    for result in results:
        score = float(result.score or 0.0)
        if not math.isfinite(score) or score <= 0:
            continue
        node = result.node
        meta = node.metadata or {}
        hits.append(Hit(
            score, node.get_content(), str(meta.get("file_path", "")),
            str(meta.get("rel_path", "")), str(meta.get("title", "")),
            str(meta.get("project", project.name)), node.node_id or "",
            cached.generation, cached.indexed_at, list(cached.wiki_roots),
        ))
    return QueryHits(
        hits, generation=cached.generation, indexed_at=cached.indexed_at,
        wiki_roots=cached.wiki_roots,
    )


def read_passage(
    project: Project,
    home: Path,
    generation: str,
    chunk_id: str,
) -> dict[str, Any]:
    """Read one indexed chunk by generation and chunk ID, never by file path."""
    if not isinstance(generation, str) or not re.fullmatch(r"[0-9a-f]{32}", generation):
        raise ValueError("generation must be a 32-character index generation")
    if not isinstance(chunk_id, str) or not re.fullmatch(r"[0-9a-f]{64}", chunk_id):
        raise ValueError("chunk_id must be a 64-character indexed chunk ID")
    meta = read_meta(project, home)
    current = meta.get("generation") if meta else None
    if generation != current or _generation_path(project.index_path(home), meta) is None:
        raise StaleGenerationError(generation, current if isinstance(current, str) else None)
    cached = _cached_retriever(project, home)
    if cached.generation != generation or cached.retriever is None:
        raise StaleGenerationError(generation, cached.generation)
    for item in cached.retriever.corpus:
        if item.get("node_id") != chunk_id:
            continue
        node = metadata_dict_to_node(item)
        metadata = node.metadata or {}
        return {
            "text": node.get_content(),
            "file_path": str(metadata.get("file_path", "")),
            "rel_path": str(metadata.get("rel_path", "")),
            "title": str(metadata.get("title", "")),
            "project": str(metadata.get("project", project.name)),
            "chunk_id": chunk_id,
            "generation": cached.generation,
            "indexed_at": cached.indexed_at,
            "wiki_roots": list(cached.wiki_roots),
        }
    raise ValueError(f"Unknown passage reference for chunk_id {chunk_id!r}")


def has_index(project: Project, home: Path) -> bool:
    folder = project.index_path(home)
    return (_generation_path(folder, read_meta(project, home)) is not None
            or (folder / _DOCS_FILENAME).is_file())


def read_meta(project: Project, home: Path) -> dict[str, Any] | None:
    try:
        meta = json.loads((project.index_path(home) / _META_FILENAME).read_text(encoding="utf-8"))
        return meta if isinstance(meta, dict) else None
    except (OSError, ValueError):
        return None


def index_all(registry: Registry, force: bool = False) -> list[IndexStats]:
    """Refresh current sources, including indexes whose source roots were removed."""
    return [index_project(project, registry.home, force=force)
            for project in registry.projects
            if project.has_any_sources() or has_index(project, registry.home)]
