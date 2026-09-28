#!/usr/bin/env python
"""Publish the front-end from NED to the separate ned-frontend repo.

NED is the single source of truth for the front-end *code* (authored in ``ui/``)
and for the database (built by ``manage.py ingest``). This script pushes both
into a clone of the deployment repo (ned-frontend):

    1. Refuse to run if ``ui/``, ``pyproject.toml``, or ``uv.lock`` has
       uncommitted changes, so the published files correspond to the NED
       commit reported at the end.
    2. Export ``requirements.txt`` from ``uv.lock`` (the ``ui`` dependency
       group), so the front-end repo receives the same pinned versions NED
       tests against. The file is generated for publishing only and is never
       committed to NED; the front-end repo's history is its record.
    3. Replace the NED-owned code paths (``OWNS``) in the front-end repo.
    4. Write the exported ``requirements.txt`` to the front-end repo root.
    5. Inject the freshly built ``db.sqlite3`` at ``backend/db.sqlite3``.

Steps 1 and 2 can fail, so both finish before anything is written to the
front-end repo. The script makes no writes inside NED itself, apart from
``--rebuild-db`` rebuilding the database.

Everything is written to the front-end repo's working tree only; staging,
committing, and pushing are left to you to do manually.

It is deliberately *non-destructive*: it only ever writes the paths listed in
``OWNS`` plus ``requirements.txt`` and ``backend/db.sqlite3``. Anything else in
the front-end repo -- ``deploy/``, ``.gcloudignore``, ``.streamlit/secrets.toml``,
and whatever the deployment owner adds later -- is left untouched. The script
describes only what NED owns, never what the front-end owns.

Usage (run from anywhere; paths are resolved relative to this file):

    python scripts/export_frontend.py --frontend ../ned-frontend
    python scripts/export_frontend.py --frontend ../ned-frontend --rebuild-db
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Same directory as this script, so a plain `python scripts/export_frontend.py`
# finds it. Owns the uv command that generates requirements.txt, so the flags
# here and in the README cannot drift apart.
from export_requirements import regenerate

NED = Path(__file__).resolve().parent.parent
UI = NED / 'ui'
DB = NED / 'db.sqlite3'

# Paths NED owns and publishes to the front-end repo. Directories are replaced
# wholesale (so deletions in ui/ propagate); files are overwritten in place.
# This is the ONLY list to maintain, and it only changes when you add a new
# top-level front-end code path -- i.e. your own code, never the deploy side.
OWNS = [
    'app.py',
    'auth.py',
    'db.py',
    'styles.py',
    'utils.py',
    'README.md',
    '.gitignore',
    '.streamlit/config.toml',
    'assets',
    'views',
]

# Generated from uv.lock at publish time; never committed to NED.
REQUIREMENTS_DEST = 'requirements.txt'

# Built into the front-end repo for deployment; gitignored / untracked in NED.
DB_DEST = 'backend/db.sqlite3'

# NED paths whose uncommitted changes would make the published files differ
# from the NED commit reported at the end: the UI code and the dependency pins.
PUBLISHED_SOURCES = ['ui', 'pyproject.toml', 'uv.lock']

# Safety net: never publish anything that looks like a credential into the repo.
_SECRET_HINTS = ('secret', '.env')


def run(cmd: list[str], cwd: Path) -> None:
    print('+', ' '.join(str(c) for c in cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def _dirty_sources() -> list[str]:
    """``git status`` lines for uncommitted changes to ``PUBLISHED_SOURCES``.

    Includes untracked files, which would be published without being in the
    reported commit. Gitignored files (``__pycache__``) are not reported.
    """
    out = subprocess.check_output(
        ['git', 'status', '--porcelain', '--', *PUBLISHED_SOURCES], cwd=NED
    ).decode()
    return out.splitlines()


def _copy(src: Path, dst: Path) -> None:
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__'))
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        '--frontend',
        required=True,
        type=Path,
        help='path to a clone of the ned-frontend repo',
    )
    ap.add_argument(
        '--rebuild-db',
        action='store_true',
        help='run `manage.py migrate` + `ingest` before exporting',
    )
    args = ap.parse_args()

    fe = args.frontend.resolve()
    if not (fe / '.git').exists():
        sys.exit(f'error: {fe} is not a git repository')

    for path in OWNS:
        if any(hint in path.lower() for hint in _SECRET_HINTS):
            sys.exit(f'error: OWNS contains a secret-shaped path: {path!r}')

    # 1. The closing message reports the NED commit the export came from; an
    # uncommitted change to the UI or the lock would not be in that commit.
    dirty = _dirty_sources()
    if dirty:
        listing = '\n'.join(f'         {line}' for line in dirty)
        sys.exit(
            'error: uncommitted changes in NED would be published under a '
            'commit that does not contain them:\n'
            f'{listing}\n'
            '       Commit or stash them, then re-run this script.\n'
            '       Nothing was written to the front-end repo.'
        )

    for path in OWNS:
        if not (UI / path).exists():
            sys.exit(f'error: ui/{path} is missing; cannot export an incomplete UI')

    if args.rebuild_db:
        run([sys.executable, 'manage.py', 'migrate'], cwd=NED)
        run([sys.executable, 'manage.py', 'ingest'], cwd=NED)

    if not DB.exists():
        sys.exit(
            f'error: {DB} not found. Build it first '
            '(`python manage.py migrate && python manage.py ingest`) '
            'or pass --rebuild-db.'
        )

    with tempfile.TemporaryDirectory() as tmp:
        # 2. Export the pinned requirements from the lock. This exits on
        # failure (e.g. a stale lock), and nothing has been written to the
        # front-end repo yet, so it is safe to stop here.
        requirements = Path(tmp) / REQUIREMENTS_DEST
        regenerate(requirements)

        # 3. Publish NED-owned code paths.
        for path in OWNS:
            _copy(UI / path, fe / path)

        # 4. Publish the requirements alongside the code.
        _copy(requirements, fe / REQUIREMENTS_DEST)

    # 5. Inject the database.
    _copy(DB, fe / DB_DEST)

    sha = (
        subprocess
        .check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=NED)
        .decode()
        .strip()
    )
    print(
        f'\nDone. Wrote UI + requirements + db from NED @ {sha} into {fe}.\n'
        'Review, stage, and commit the changes in the front-end repo manually.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
