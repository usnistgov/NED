#!/usr/bin/env python
"""Publish the front-end from NED to the separate ned-frontend repo.

NED is the single source of truth for the front-end *code* (authored in ``ui/``)
and for the database (built by ``manage.py ingest``). This script pushes both
into a clone of the deployment repo (ned-frontend):

    1. Regenerate ``ui/requirements.txt`` from ``uv.lock`` (the ``ui``
       dependency group), so the front-end repo receives the same pinned
       versions NED tests against.
    2. Replace the NED-owned code paths (``OWNS``) in the front-end repo.
    3. Inject the freshly built ``db.sqlite3`` at ``backend/db.sqlite3``.

Step 1 is the one write this script makes inside NED itself. If it leaves
``ui/requirements.txt`` differing from HEAD, the script stops without touching
the front-end repo: the published files must correspond to the NED commit
reported at the end, so the regenerated file has to be committed here first.

Everything else is written to the front-end repo's working tree only; staging,
committing, and pushing are left to you to do manually.

It is deliberately *non-destructive*: it only ever writes the paths listed in
``OWNS`` plus ``backend/db.sqlite3``. Anything else in the front-end repo --
``deploy/``, ``.gcloudignore``, ``.streamlit/secrets.toml``, and whatever the
deployment owner adds later -- is left untouched. The script describes only what NED owns, never
what the front-end owns.

Usage (run from anywhere; paths are resolved relative to this file):

    python scripts/export_frontend.py --frontend ../ned-frontend
    python scripts/export_frontend.py --frontend ../ned-frontend --rebuild-db
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Same directory as this script, so a plain `python scripts/export_frontend.py`
# finds it. Owns the uv command that generates ui/requirements.txt, so the
# flags here, in CI, and in the README cannot drift apart.
from export_requirements import REQUIREMENTS, regenerate

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
    'requirements.txt',
    'README.md',
    '.gitignore',
    '.streamlit/config.toml',
    'assets',
    'views',
]

# Built into the front-end repo for deployment; gitignored / untracked in NED.
DB_DEST = 'backend/db.sqlite3'

# Safety net: never publish anything that looks like a credential into the repo.
_SECRET_HINTS = ('secret', '.env')


def run(cmd: list[str], cwd: Path) -> None:
    print('+', ' '.join(str(c) for c in cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def _differs_from_head(path: str) -> bool:
    """True if ``path``'s content differs from the committed version in NED.

    Compares line by line rather than byte for byte, and reads the committed
    blob directly, so the answer does not depend on ``core.autocrlf``: a
    checkout that put CRLF in the working tree is not a difference in the
    pinned versions, which is the only thing that matters here.
    """
    try:
        committed = subprocess.check_output(
            ['git', 'show', f'HEAD:{path}'], cwd=NED, stderr=subprocess.DEVNULL
        ).decode()
    except subprocess.CalledProcessError:
        return True  # not in HEAD yet, so it needs committing
    current = (NED / path).read_text(encoding='utf-8')
    return committed.splitlines() != current.splitlines()


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

    if args.rebuild_db:
        run([sys.executable, 'manage.py', 'migrate'], cwd=NED)
        run([sys.executable, 'manage.py', 'ingest'], cwd=NED)

    if not DB.exists():
        sys.exit(
            f'error: {DB} not found. Build it first '
            '(`python manage.py migrate && python manage.py ingest`) '
            'or pass --rebuild-db.'
        )

    # 1. Regenerate the pinned requirements from the lock.
    regenerate()

    # Nothing has been written to the front-end repo yet, so it is safe to stop
    # here. The closing message reports the NED commit the export came from; if
    # ui/requirements.txt does not match HEAD, that commit would not describe
    # what was published, and CI would fail on the same difference.
    if _differs_from_head(REQUIREMENTS):
        sys.exit(
            f'error: {REQUIREMENTS} differs from HEAD after regenerating it '
            'from uv.lock.\n'
            f'       Review the change (`git diff -- {REQUIREMENTS}`), commit '
            'it, then re-run this script.\n'
            '       Nothing was written to the front-end repo.'
        )

    # 2. Publish NED-owned code paths.
    for path in OWNS:
        src = UI / path
        if not src.exists():
            sys.exit(f'error: ui/{path} is missing; cannot export an incomplete UI')
        _copy(src, fe / path)

    # 3. Inject the database.
    _copy(DB, fe / DB_DEST)

    sha = (
        subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=NED)
        .decode()
        .strip()
    )
    print(
        f'\nDone. Wrote UI + db from NED @ {sha} into {fe}.\n'
        'Review, stage, and commit the changes in the front-end repo manually.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
