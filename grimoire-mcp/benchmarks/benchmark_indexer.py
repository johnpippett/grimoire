"""Measure a temporary 100-document wiki; run with the installed package Python.

Reports end-to-end build, unchanged refresh, cold/warm query wall time and
process peak RSS (Linux/macOS). No source projects or persistent indexes change.
"""
import json
from pathlib import Path
import resource
import statistics
import sys
import tempfile
import time

from wiki_rag.config import Project
from wiki_rag.indexer import index_project, query_project


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        wiki = root / 'wiki'
        wiki.mkdir()
        for number in range(100):
            body = f'Service {number} deployment rollback database migration monitoring configuration. '
            (wiki / f'{number}.md').write_text(f'# Service {number}\n\n' + body * 60)
        project = Project('benchmark', root, [wiki])
        home = root / 'derived'
        started = time.perf_counter()
        index_project(project, home)
        build = time.perf_counter() - started
        started = time.perf_counter()
        index_project(project, home)
        refresh = time.perf_counter() - started
        latencies = []
        for _ in range(6):
            started = time.perf_counter()
            query_project(project, home, 'deployment rollback', top_k=5)
            latencies.append(time.perf_counter() - started)
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print(json.dumps({
            'documents': 100,
            'build_s': build,
            'unchanged_refresh_s': refresh,
            'cold_query_s': latencies[0],
            'warm_median_s': statistics.median(latencies[1:]),
            'peak_rss_mb': rss / (1024 * 1024 if sys.platform == 'darwin' else 1024),
        }))


if __name__ == '__main__':
    main()
