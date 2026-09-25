"""Regression coverage for persisted retrieval and refresh publication."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from wiki_rag import indexer
from wiki_rag.config import Project


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / 'project'
    wiki = root / 'wiki'
    wiki.mkdir(parents=True)
    (wiki / 'one.md').write_text('# Cobalt\nCobalt reactor maintenance instructions.', encoding='utf-8')
    (wiki / 'two.md').write_text('# Orchards\nApples and orange harvesting.', encoding='utf-8')
    return Project('example', root, [wiki]), tmp_path / 'home'


def test_persisted_queries_do_not_chunk_or_build_and_keep_ids(corpus):
    project, home = corpus
    indexer.index_project(project, home)
    with patch.object(indexer.SentenceSplitter, 'get_nodes_from_documents', side_effect=AssertionError('query rechunked')), patch.object(indexer.BM25Retriever, 'from_defaults', side_effect=AssertionError('query rebuilt')):
        first = indexer.query_project(project, home, 'cobalt', top_k=25)
        second = indexer.query_project(project, home, 'cobalt', top_k=1)
    assert len(first) == 1
    assert len(second) == 1
    assert first[0].rel_path == 'wiki/one.md'
    assert first[0].chunk_id == second[0].chunk_id
    assert first[0].score > 0
    assert first[0].generation == indexer.read_meta(project, home)['generation']
    assert first[0].wiki_roots == [str(project.wiki_roots[0])]
    assert first[0].indexed_at == indexer.read_meta(project, home)['indexed_at']
    indexer.index_project(project, home, force=True)
    assert indexer.query_project(project, home, 'cobalt', 1)[0].chunk_id == first[0].chunk_id


def test_query_omits_zero_scores_and_rejects_top_k_above_25(corpus):
    project, home = corpus
    indexer.index_project(project, home)

    assert indexer.query_project(project, home, 'unfindablezymotif', top_k=25) == []
    with pytest.raises(ValueError, match='top_k'):
        indexer.query_project(project, home, 'cobalt', top_k=26)


def test_unchanged_refresh_skips_preparation_and_keeps_generation(corpus):
    project, home = corpus
    indexer.index_project(project, home)
    before = indexer.read_meta(project, home)
    with patch.object(indexer.SentenceSplitter, 'get_nodes_from_documents', side_effect=AssertionError('unchanged rechunked')):
        stats = indexer.index_project(project, home)
    assert stats.unchanged
    assert stats.files_indexed == 2
    assert indexer.read_meta(project, home) == before


def test_edits_deletions_and_settings_invalidate(corpus):
    project, home = corpus
    indexer.index_project(project, home)
    original = indexer.read_meta(project, home)
    (project.wiki_roots[0] / 'one.md').write_text('# Zircon\nZircon reactor guidance.', encoding='utf-8')
    (project.wiki_roots[0] / 'two.md').unlink()
    assert not indexer.index_project(project, home).unchanged
    assert indexer.read_meta(project, home)['generation'] != original['generation']
    hits = indexer.query_project(project, home, 'zircon', 10)
    assert len(hits) == 1 and 'Zircon' in hits[0].text
    with patch.object(indexer, '_CHUNK_SIZE', 512):
        assert not indexer.index_project(project, home).unchanged


def test_failed_publication_keeps_previous_queryable(corpus):
    project, home = corpus
    indexer.index_project(project, home)
    before = indexer.read_meta(project, home)
    (project.wiki_roots[0] / 'one.md').write_text('# Changed\nChanged content', encoding='utf-8')
    with patch.object(indexer.BM25Retriever, 'persist', side_effect=OSError('disk full')):
        with pytest.raises(OSError, match='disk full'):
            indexer.index_project(project, home)
    assert indexer.read_meta(project, home) == before
    assert 'Cobalt' in indexer.query_project(project, home, 'cobalt', 1)[0].text


def test_empty_and_invalid_queries(corpus):
    project, home = corpus
    for path in project.list_source_files():
        path.unlink()
    assert indexer.index_project(project, home).chunks == 0
    assert indexer.has_index(project, home)
    assert indexer.query_project(project, home, 'anything') == []
    with pytest.raises(ValueError):
        indexer.query_project(project, home, ' ')
    with pytest.raises(ValueError):
        indexer.query_project(project, home, 'anything', 0)


def test_concurrent_queries_have_independent_limits(corpus):
    project, home = corpus
    (project.wiki_roots[0] / 'two.md').write_text('# Orchards\nCobalt orchard apples and orange harvesting.', encoding='utf-8')
    indexer.index_project(project, home)
    with ThreadPoolExecutor(max_workers=4) as executor:
        lengths = list(executor.map(lambda k: len(indexer.query_project(project, home, 'cobalt', k)), [1, 2] * 8))
    assert lengths == [1, 2] * 8


def test_legacy_index_migrates(corpus):
    project, home = corpus
    folder = project.index_path(home)
    folder.mkdir(parents=True)
    (folder / 'documents.jsonl').write_text(json.dumps({'text': 'old', 'metadata': {}}) + '\n')
    (folder / 'index.json').write_text(json.dumps({'indexer_version': 1}))
    assert indexer.has_index(project, home)
    assert 'Cobalt' in indexer.query_project(project, home, 'cobalt', 1)[0].text
    assert indexer.read_meta(project, home)['indexer_version'] == 2


def test_external_refresh_invalidates_cache(corpus):
    import os
    import subprocess
    import sys
    project, home = corpus
    indexer.index_project(project, home)
    assert 'Cobalt' in indexer.query_project(project, home, 'cobalt', 1)[0].text
    (project.wiki_roots[0] / 'one.md').write_text('# Zircon\nZircon mineral specimen.', encoding='utf-8')
    source = "from pathlib import Path; from wiki_rag.config import Project; from wiki_rag.indexer import index_project; import sys; p=Path(sys.argv[1]); index_project(Project('example',p,[p/'wiki']),Path(sys.argv[2]))"
    subprocess.run([sys.executable, '-c', source, str(project.root), str(home)], check=True, env=os.environ.copy(), timeout=30)
    assert 'Zircon' in indexer.query_project(project, home, 'zircon', 1)[0].text


def test_retriever_cache_reuses_and_evicts(corpus):
    project, home = corpus
    indexer.index_project(project, home)
    indexer._CACHE.clear()
    with patch.object(indexer, '_CACHE_MAX_PROJECTS', 1), patch.object(indexer.BM25Retriever, 'from_persist_dir', wraps=indexer.BM25Retriever.from_persist_dir) as load:
        indexer.query_project(project, home, 'cobalt', 1)
        indexer.query_project(project, home, 'apples', 2)
        assert load.call_count == 1
        second_home = home.parent / 'other-home'
        indexer.index_project(project, second_home)
        indexer.query_project(project, second_home, 'cobalt', 1)
        indexer.query_project(project, home, 'cobalt', 1)
        assert load.call_count == 3
        assert len(indexer._CACHE) == 1


def test_metadata_pointer_stays_small(corpus):
    project, home = corpus
    indexer.index_project(project, home)
    meta = indexer.read_meta(project, home)
    assert 'manifest' not in meta
    assert (project.index_path(home) / 'generations' / meta['generation'] / 'manifest.json').is_file()


def test_slow_cold_load_does_not_block_unrelated_warm_query(corpus):
    import threading
    project, home = corpus
    other_home = home.parent / 'other-home'
    indexer.index_project(project, home)
    indexer.index_project(project, other_home)
    indexer.query_project(project, home, 'cobalt', 1)
    started, release = threading.Event(), threading.Event()
    original = indexer.BM25Retriever.from_persist_dir

    def slow_load(*args, **kwargs):
        started.set()
        assert release.wait(5), 'cold loader was never released'
        return original(*args, **kwargs)

    with ThreadPoolExecutor(max_workers=2) as executor, patch.object(indexer.BM25Retriever, 'from_persist_dir', side_effect=slow_load):
        cold = executor.submit(indexer.query_project, project, other_home, 'cobalt', 1)
        try:
            assert started.wait(5)
            warm = executor.submit(indexer.query_project, project, home, 'cobalt', 1)
            assert 'Cobalt' in warm.result(timeout=1)[0].text
        finally:
            release.set()
        assert cold.result(timeout=5)


def test_cross_process_writers_publish_one_generation(corpus):
    import os
    import subprocess
    import sys
    project, home = corpus
    source = "from pathlib import Path; from wiki_rag.config import Project; from wiki_rag.indexer import index_project; import sys; p=Path(sys.argv[1]); print(index_project(Project('example',p,[p/'wiki']),Path(sys.argv[2])).unchanged)"
    processes = [subprocess.Popen([sys.executable, '-c', source, str(project.root), str(home)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ.copy()) for _ in range(2)]
    outputs = [process.communicate(timeout=30) for process in processes]
    assert all(process.returncode == 0 for process in processes), outputs
    assert sorted(stdout.strip() for stdout, _ in outputs) == ['False', 'True']
    generations = list((project.index_path(home) / 'generations').iterdir())
    assert len(generations) == 1
    assert 'Cobalt' in indexer.query_project(project, home, 'cobalt', 1)[0].text


def test_byte_budget_does_not_admit_large_retriever(corpus):
    project, home = corpus
    indexer.index_project(project, home)
    indexer._CACHE.clear()
    with patch.object(indexer, '_CACHE_MAX_BYTES', 1):
        assert indexer.query_project(project, home, 'cobalt', 1)
        assert not indexer._CACHE


def test_removing_all_source_roots_clears_existing_index(corpus):
    import shutil
    from wiki_rag.config import Registry
    project, home = corpus
    indexer.index_project(project, home)
    shutil.rmtree(project.wiki_roots[0])
    rediscovered = Project(project.name, project.root, [])
    stats = indexer.index_all(Registry(project.root.parent, home, [rediscovered]))
    assert len(stats) == 1 and stats[0].chunks == 0
    assert indexer.query_project(rediscovered, home, 'cobalt') == []


def test_hash_detects_edit_with_preserved_file_metadata(corpus):
    import os
    project, home = corpus
    indexer.index_project(project, home)
    path = project.wiki_roots[0] / 'one.md'
    stat = path.stat()
    path.write_text(path.read_text().replace('Cobalt', 'Zircon'), encoding='utf-8')
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert path.stat().st_size == stat.st_size
    assert not indexer.index_project(project, home).unchanged
    assert 'Zircon' in indexer.query_project(project, home, 'zircon', 1)[0].text


def test_long_notes_index_without_nltk_runtime_import(corpus):
    """Long notes must work offline and with project-local runtime dependencies."""
    import sys
    project, home = corpus
    text = '# Long operations note\n' + ('Deployment instructions are recorded here. ' * 700) + 'Zebramarker recovery procedure.'
    (project.wiki_roots[0] / 'long.md').write_text(text, encoding='utf-8')
    with patch.dict(sys.modules, {'nltk': None}):
        stats = indexer.index_project(project, home)
        hits = indexer.query_project(project, home, 'Zebramarker', top_k=1)
    assert stats.chunks > stats.files_indexed
    assert hits[0].rel_path == 'wiki/long.md'
    assert 'Zebramarker recovery procedure.' in hits[0].text
