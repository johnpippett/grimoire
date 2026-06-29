"""Indexing and retrieval for wiki-rag-mcp.

We persist the raw documents per project (JSONL of file text + metadata) and
build a LlamaIndex ``BM25Retriever`` on top of those nodes at query time.

BM25 was chosen over a vector retriever for two reasons:

1. **Zero ML dependencies.** No embedding model download, no GPU, no first-run
   stall. Works on the first call.
2. **Deterministic.** Same query -> same result. Easy to debug and unit test.

The persisted representation is a thin JSONL file per project, which is
trivial to inspect, diff, and re-create. The LlamaIndex layer is responsible
for chunking, node construction, and the retriever itself.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llama_index.core import Document, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.retrievers.bm25 import BM25Retriever

from .config import Project, Registry

logger = logging.getLogger(__name__)

# Don't let llama-index touch the global Settings; we want deterministic,
# dependency-free indexing. Reset just in case the host process has set
# an embedding model that requires network.
# Use stdout redirect to suppress the loud "explicitly disabled" print()s
# that the llama utils emit on None assignment.
import sys, io
_old_stdout = sys.stdout
sys.stdout = io.StringIO()
try:
    Settings.embed_model = None
    Settings.llm = None
finally:
    sys.stdout = _old_stdout


_DOCS_FILENAME = "documents.jsonl"
_META_FILENAME = "index.json"
# Tokenization rough budget for BM25. ~256 tokens / ~1024 chars.
_CHUNK_SIZE = 1024
_CHUNK_OVERLAP = 128


@dataclass
class IndexStats:
    project: str
    files_indexed: int
    files_skipped: int
    chunks: int
    bytes_indexed: int
    duration_s: float
    skipped: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "files_indexed": self.files_indexed,
            "files_skipped": self.files_skipped,
            "chunks": self.chunks,
            "bytes_indexed": self.bytes_indexed,
            "duration_s": round(self.duration_s, 3),
            "skipped": self.skipped,
        }


def _index_dir(project: Project, home: Path) -> Path:
    path = project.index_path(home)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _extract_title(text: str, fallback: str) -> str:
    """Pick the first markdown H1 or the first non-empty line as a title."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        m = re.match(r"^#\s+(.+)$", stripped)
        if m:
            return m.group(1).strip()
        return stripped[:120]
    return fallback


def index_project(project: Project, home: Path) -> IndexStats:
    """Build (or rebuild) the on-disk index for ``project``."""
    start = time.perf_counter()
    files = project.list_source_files()
    docs: list[Document] = []
    skipped: list[dict[str, str]] = []
    bytes_total = 0
    files_indexed = 0

    for path in files:
        try:
            text = _read_text(path)
        except OSError as exc:
            skipped.append({"file": str(path), "reason": f"read error: {exc}"})
            continue
        if not text.strip():
            skipped.append({"file": str(path), "reason": "empty"})
            continue
        bytes_total += len(text.encode("utf-8"))
        rel = str(path.relative_to(project.root)) if path.is_relative_to(project.root) else str(path)
        title = _extract_title(text, path.stem)
        doc = Document(
            text=text,
            metadata={
                "project": project.name,
                "file_path": str(path),
                "rel_path": rel,
                "title": title,
            },
            excluded_llm_metadata_keys=["file_path"],
            excluded_embed_metadata_keys=["file_path"],
        )
        docs.append(doc)
        files_indexed += 1

    splitter = SentenceSplitter(chunk_size=_CHUNK_SIZE, chunk_overlap=_CHUNK_OVERLAP)
    nodes = splitter.get_nodes_from_documents(docs) if docs else []

    out_dir = _index_dir(project, home)
    docs_path = out_dir / _DOCS_FILENAME
    with docs_path.open("w", encoding="utf-8") as f:
        for doc in docs:
            f.write(
                json.dumps(
                    {
                        "text": doc.text,
                        "metadata": dict(doc.metadata),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    meta = {
        "project": project.name,
        "slug": project.slug,
        "wiki_roots": [str(p) for p in project.wiki_roots],
        "files_indexed": files_indexed,
        "files_skipped": len(skipped),
        "chunks": len(nodes),
        "bytes_indexed": bytes_total,
        "indexed_at": int(time.time()),
        "indexer_version": 1,
    }
    (out_dir / _META_FILENAME).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    duration = time.perf_counter() - start
    stats = IndexStats(
        project=project.name,
        files_indexed=files_indexed,
        files_skipped=len(skipped),
        chunks=len(nodes),
        bytes_indexed=bytes_total,
        duration_s=duration,
        skipped=skipped,
    )
    logger.info(
        "indexed %s: %d files, %d chunks, %d bytes in %.2fs",
        project.name,
        files_indexed,
        len(nodes),
        bytes_total,
        duration,
    )
    return stats


def _load_documents(project: Project, home: Path) -> list[Document]:
    docs_path = project.index_path(home) / _DOCS_FILENAME
    if not docs_path.exists():
        raise FileNotFoundError(
            f"No index for {project.name!r}. Run reindex_project first."
        )
    docs: list[Document] = []
    with docs_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            doc = Document(
                text=obj["text"],
                metadata=obj.get("metadata") or {},
                excluded_llm_metadata_keys=["file_path"],
                excluded_embed_metadata_keys=["file_path"],
            )
            docs.append(doc)
    return docs


@dataclass
class Hit:
    score: float
    text: str
    file_path: str
    rel_path: str
    title: str
    project: str
    chunk_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "text": self.text,
            "file_path": self.file_path,
            "rel_path": self.rel_path,
            "title": self.title,
            "project": self.project,
            "chunk_id": self.chunk_id,
        }


def query_project(
    project: Project,
    home: Path,
    question: str,
    top_k: int = 5,
) -> list[Hit]:
    """Return the top-k BM25 hits for ``question`` within ``project``."""
    if not question or not question.strip():
        raise ValueError("question must be a non-empty string")

    docs = _load_documents(project, home)
    if not docs:
        return []

    splitter = SentenceSplitter(chunk_size=_CHUNK_SIZE, chunk_overlap=_CHUNK_OVERLAP)
    nodes = splitter.get_nodes_from_documents(docs)
    retriever = BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=top_k)
    results = retriever.retrieve(question)

    hits: list[Hit] = []
    for node_with_score in results:
        node = node_with_score.node
        meta = node.metadata or {}
        hits.append(
            Hit(
                score=float(node_with_score.score or 0.0),
                text=node.get_content(),
                file_path=str(meta.get("file_path", "")),
                rel_path=str(meta.get("rel_path", "")),
                title=str(meta.get("title", "")),
                project=str(meta.get("project", project.name)),
                chunk_id=node.node_id or "",
            )
        )
    return hits


def has_index(project: Project, home: Path) -> bool:
    return (project.index_path(home) / _DOCS_FILENAME).exists()


def read_meta(project: Project, home: Path) -> dict[str, Any] | None:
    path = project.index_path(home) / _META_FILENAME
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def index_all(registry: Registry) -> list[IndexStats]:
    """Index every project that has any wiki sources. Returns per-project stats."""
    out: list[IndexStats] = []
    for project in registry.projects:
        if not project.has_any_sources():
            logger.info("skip %s: no wiki roots", project.name)
            continue
        out.append(index_project(project, registry.home))
    return out
