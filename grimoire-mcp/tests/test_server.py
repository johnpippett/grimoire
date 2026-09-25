import asyncio
import json
import threading
import time
from unittest.mock import patch

from wiki_rag import server
from wiki_rag.config import Project


def configure(tmp_path, monkeypatch):
    root = tmp_path / 'projects'
    root.mkdir()
    monkeypatch.setenv('WIKI_RAG_PROJECTS_ROOT', str(root))
    monkeypatch.setenv('WIKI_RAG_HOME', str(tmp_path / 'home'))
    monkeypatch.setattr(server, '_REGISTRY', None)
    return root


def listing(**args):
    return json.loads(asyncio.run(server.call_tool('list_projects', args))[0].text)


def call_text(name, **args):
    return asyncio.run(server.call_tool(name, args))[0].text


def call_json(name, **args):
    return json.loads(call_text(name, **args))


def test_default_listing_does_not_walk_sources(tmp_path, monkeypatch):
    root = configure(tmp_path, monkeypatch)
    (root / 'example' / 'wiki').mkdir(parents=True)
    with patch.object(Project, 'list_source_files', side_effect=AssertionError('recursive scan')):
        result = listing()
    assert result['count'] == 1
    assert result['projects'][0]['source_files'] is None
    assert result['projects'][0]['source_files_basis'] == 'unknown'


def test_listing_uses_indexed_counts_and_live_scan_is_explicit(tmp_path, monkeypatch):
    root = configure(tmp_path, monkeypatch)
    wiki = root / 'example' / 'wiki'
    wiki.mkdir(parents=True)
    (wiki / 'new.md').write_text('new source')
    with patch.object(server.indexer, 'read_meta', return_value={'files_indexed': 3, 'indexed_at': 'yesterday'}):
        cached = listing()['projects'][0]
        live = listing(live_scan=True)['projects'][0]
    assert cached['source_files'] == 3
    assert cached['source_files_basis'] == 'indexed'
    assert cached['source_files_at'] == 'yesterday'
    assert live['source_files'] == 1
    assert live['source_files_basis'] == 'live'
    assert live['source_files_at'] != 'yesterday'


def test_listing_refreshes_new_projects_and_overrides(tmp_path, monkeypatch):
    root = configure(tmp_path, monkeypatch)
    assert listing()['count'] == 0
    (root / 'new' / 'wiki').mkdir(parents=True)
    assert listing()['count'] == 1
    (tmp_path / 'home' / 'projects.json').write_text(json.dumps({'exclude': ['new']}))
    assert listing()['count'] == 0


def test_slow_listing_does_not_block_event_loop(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    original = server.load_registry
    def slow_load():
        time.sleep(0.15)
        return original()
    monkeypatch.setattr(server, 'load_registry', slow_load)
    async def scenario():
        task = asyncio.create_task(server.call_tool('list_projects', {}))
        await asyncio.sleep(0.02)
        assert not task.done(), 'filesystem work blocked the event loop'
        await task
    asyncio.run(scenario())


def test_cancelled_requests_keep_worker_concurrency_bounded(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    active = peak = submitted = peak_submitted = 0
    lock = threading.Lock()
    original_submit = server._WORKERS.submit
    def submit(*args, **kwargs):
        nonlocal submitted, peak_submitted
        with lock:
            submitted += 1
            peak_submitted = max(peak_submitted, submitted)
        future = original_submit(*args, **kwargs)
        def finished(_future):
            nonlocal submitted
            with lock:
                submitted -= 1
        future.add_done_callback(finished)
        return future
    monkeypatch.setattr(server._WORKERS, 'submit', submit)
    original = server.load_registry
    def slow_load():
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(0.1)
            return original()
        finally:
            with lock:
                active -= 1
    monkeypatch.setattr(server, 'load_registry', slow_load)
    async def scenario():
        requests = []
        for _ in range(12):
            task = asyncio.create_task(server.call_tool('list_projects', {}))
            requests.append(task)
            await asyncio.sleep(0.002)
            task.cancel()
        await asyncio.gather(*requests, return_exceptions=True)
        await server.call_tool('list_projects', {})
    started = time.monotonic()
    asyncio.run(scenario())
    assert peak <= 4
    assert peak_submitted <= 4, "cancelled requests released worker slots too early"
    assert time.monotonic() - started < 1.0, 'requests blocked the event loop'


def test_reindex_refreshes_registry(tmp_path, monkeypatch):
    root = configure(tmp_path, monkeypatch)
    server._get_registry()
    (root / 'new' / 'wiki').mkdir(parents=True)
    captured = []
    def index_all(registry):
        captured.extend(registry.names())
        return []
    monkeypatch.setattr(server.indexer, 'index_all', index_all)
    asyncio.run(server.call_tool('reindex_project', {}))
    assert captured == ['new']


def test_cli_reports_unchanged_projects(tmp_path, monkeypatch, capsys):
    import sys
    from types import SimpleNamespace
    import pytest
    configure(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, 'argv', ['grimoire-mcp', 'reindex'])
    monkeypatch.setattr(server.indexer, 'index_all', lambda registry: [
        SimpleNamespace(project='old', files_indexed=2, chunks=2, unchanged=True),
        SimpleNamespace(project='new', files_indexed=1, chunks=1, unchanged=False),
    ])
    with pytest.raises(SystemExit) as exc:
        server.main()
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert 'Reindexed 1 projects; 1 unchanged.' in output
    assert 'old: unchanged' in output


def test_listing_counts_indexed_empty_files(tmp_path, monkeypatch):
    root = configure(tmp_path, monkeypatch)
    (root / 'example' / 'wiki').mkdir(parents=True)
    with patch.object(server.indexer, 'read_meta', return_value={
        'files_indexed': 2, 'source_file_count': 3, 'indexed_at': 'yesterday'
    }):
        assert listing()['projects'][0]['source_files'] == 3


def test_targeted_reindex_can_clear_removed_wiki(tmp_path, monkeypatch):
    from types import SimpleNamespace
    root = configure(tmp_path, monkeypatch)
    (root / 'removed').mkdir()
    captured = []
    monkeypatch.setattr(server.indexer, 'has_index', lambda *args: True)
    def rebuild(project, home):
        captured.append(project.name)
        return SimpleNamespace(to_dict=lambda: {'project': project.name})
    monkeypatch.setattr(server.indexer, 'index_project', rebuild)
    asyncio.run(server.call_tool('reindex_project', {'project': 'removed'}))
    assert captured == ['removed']


def test_query_response_has_bounded_provenance_and_reports_omitted_hits(tmp_path, monkeypatch):
    root = configure(tmp_path, monkeypatch)
    wiki = root / 'fixture' / 'wiki'
    wiki.mkdir(parents=True)
    for number in range(30):
        body = f"sharedneedle item {number}. " + ('Evidence details support safe operations. ' * 45)
        (wiki / f'note-{number:02}.md').write_text(f'# Note {number}\n\n{body}', encoding='utf-8')
    registry = server._get_registry(refresh=True)
    project = registry.get('fixture')
    meta = server.indexer.index_project(project, registry.home)

    response = call_json('query_wiki', project='fixture', question='sharedneedle', top_k=25)
    rendered = json.dumps(response, ensure_ascii=False, separators=(',', ':'))

    assert len(rendered) <= 8000
    assert response['generation'] == server.indexer.read_meta(project, registry.home)['generation']
    assert response['omitted_hits'] > 0
    assert response['results']
    hit = response['results'][0]
    assert hit['score'] > 0
    assert hit['file_path'].endswith('.md')
    assert hit['rel_path'].startswith('wiki/')
    assert hit['wiki_roots'] == [str(wiki)]
    assert hit['indexed_at']
    assert hit['generation']
    assert hit['chunk_id']
    assert hit['excerpt_truncated'] is True
    assert hit['next_offset'] == len(hit['text'])


def test_query_wiki_enforces_top_k_bounds(tmp_path, monkeypatch):
    root = configure(tmp_path, monkeypatch)
    wiki = root / 'fixture' / 'wiki'
    wiki.mkdir(parents=True)
    (wiki / 'note.md').write_text('# Note\nsharedneedle details.', encoding='utf-8')
    registry = server._get_registry(refresh=True)
    server.indexer.index_project(registry.get('fixture'), registry.home)

    for value in (0, 26, True, '2'):
        assert 'top_k' in call_text('query_wiki', project='fixture', question='sharedneedle', top_k=value)
    assert call_json('query_wiki', project='fixture', question='sharedneedle', top_k=1)['results']
    assert call_json('query_wiki', project='fixture', question='sharedneedle', top_k=25)['results']


def test_passage_tool_paginates_and_rejects_stale_and_unknown_references(tmp_path, monkeypatch):
    root = configure(tmp_path, monkeypatch)
    wiki = root / 'fixture' / 'wiki'
    wiki.mkdir(parents=True)
    source = wiki / 'long.md'
    source.write_text('# Long passage\n' + 'passagemarker ' * 8000, encoding='utf-8')
    registry = server._get_registry(refresh=True)
    project = registry.get('fixture')
    server.indexer.index_project(project, registry.home)
    query = call_json('query_wiki', project='fixture', question='passagemarker', top_k=1)
    reference = query['results'][0]

    first = call_json('read_wiki_passage', project='fixture', generation=reference['generation'], chunk_id=reference['chunk_id'], offset=0)
    second = call_json('read_wiki_passage', project='fixture', generation=reference['generation'], chunk_id=reference['chunk_id'], offset=first['next_offset'])
    assert len(json.dumps(first, ensure_ascii=False, separators=(',', ':'))) <= 8000
    assert first['complete'] is False
    assert second['complete'] is True
    passage = server.indexer.read_passage(project, registry.home, reference['generation'], reference['chunk_id'])
    assert first['text'] + second['text'] == passage['text']

    arbitrary_path = call_text('read_wiki_passage', project='fixture', generation=reference['generation'], chunk_id='/etc/passwd')
    assert 'chunk_id' in arbitrary_path
    unknown = call_text('read_wiki_passage', project='fixture', generation=reference['generation'], chunk_id='0' * 64)
    assert 'Unknown passage' in unknown

    source.write_text('# Long passage updated\n' + 'newpassagemarker ' * 8000, encoding='utf-8')
    server.indexer.index_project(project, registry.home)
    stale = call_json('read_wiki_passage', project='fixture', generation=reference['generation'], chunk_id=reference['chunk_id'], offset=0)
    assert stale['stale'] is True
    assert 'query again' in stale['message'].lower()


def test_passage_response_caps_json_escaped_provenance_and_advances():
    control_path = '\x01' * 1000
    passage = {
        'project': 'fixture',
        'file_path': control_path,
        'rel_path': control_path,
        'title': control_path,
        'wiki_roots': [control_path] * 8,
        'indexed_at': 123,
        'generation': 'a' * 32,
        'chunk_id': 'b' * 64,
        'text': 'passage text ' * 500,
    }

    rendered = server._passage_response(passage, offset=0)
    response = json.loads(rendered)

    assert len(rendered) <= 8000
    assert response['provenance_truncated'] is True
    assert response['complete'] is False
    assert response['next_offset'] > response['offset']
    assert response['next_offset'] == len(response['text'])


def test_no_match_response_uses_generation_that_was_queried(tmp_path, monkeypatch):
    root = configure(tmp_path, monkeypatch)
    wiki = root / 'fixture' / 'wiki'
    wiki.mkdir(parents=True)
    source = wiki / 'note.md'
    source.write_text('# Note\nKnown fixture content.', encoding='utf-8')
    registry = server._get_registry(refresh=True)
    project = registry.get('fixture')
    server.indexer.index_project(project, registry.home)
    before = server.indexer.read_meta(project, registry.home)
    original_query = server.indexer.query_project

    def query_then_reindex(*args, **kwargs):
        hits = original_query(*args, **kwargs)
        assert hits == []
        source.write_text('# Note\nChanged fixture content.', encoding='utf-8')
        server.indexer.index_project(project, registry.home)
        return hits

    monkeypatch.setattr(server.indexer, 'query_project', query_then_reindex)
    response = call_json('query_wiki', project='fixture', question='unfindablezymotif', top_k=5)

    after = server.indexer.read_meta(project, registry.home)
    assert after['generation'] != before['generation']
    assert response['generation'] == before['generation']
    assert response['indexed_at'] == before['indexed_at']
