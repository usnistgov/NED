#!/usr/bin/env python
"""Generate ``ui/requirements.txt`` from ``uv.lock``.

The front-end deployment repo installs the UI with plain pip, so it needs a
pinned ``requirements.txt`` rather than a lock file. That file is generated,
never hand-edited, and this module owns the one command that generates it.

Three callers share it, so the flags cannot drift apart between them:

    * ``scripts/export_frontend.py``, before publishing to the front-end repo.
    * The ``UI Requirements Match Lock`` CI job, via ``--check``.
    * Maintainers regenerating by hand after editing the ``ui`` group.

Usage (run from anywhere; paths are resolved relative to this file):

    python scripts/export_requirements.py            # rewrite the file
    python scripts/export_requirements.py --check    # verify, change nothing
"""

from __future__ import annotations

import argparse
import difflib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NED = Path(__file__).resolve().parent.parent

# Generated from the lock, published to the front-end repo, checked by CI.
# Relative to NED so it can be handed to uv, git, and difflib alike.
REQUIREMENTS = 'ui/requirements.txt'


def export_cmd(dest: str) -> list[str]:
    """The uv invocation that writes the pinned requirements to ``dest``.

    ``--locked`` refuses a lock that is out of date with pyproject.toml, so a
    stale pin can never be published. The remaining flags strip everything that
    is not a pinned requirement, because pip is the only consumer.
    """
    return [
        'uv',
        'export',
        '--locked',
        '--format',
        'requirements.txt',
        '--only-group',
        'ui',
        '--no-hashes',
        '--no-annotate',
        '--no-header',
        '-o',
        dest,
    ]


def require_uv() -> None:
    """Exit with a clear message if uv is not available."""
    if shutil.which('uv') is None:
        sys.exit(
            f'error: uv is not on PATH; it is needed to generate {REQUIREMENTS}'
        )


def _run_export(dest: str) -> None:
    cmd = export_cmd(dest)
    print('+', ' '.join(cmd))
    try:
        # uv echoes the requirements to stdout as well as writing them to
        # dest; that duplicates the file and, under --check, buries the diff.
        subprocess.run(cmd, cwd=NED, check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as exc:
        sys.exit(f'error: uv export failed with exit status {exc.returncode}')


def regenerate() -> None:
    """Rewrite ``ui/requirements.txt`` in place from the lock."""
    require_uv()
    _run_export(REQUIREMENTS)


def check() -> int:
    """Report whether the committed file matches the lock. Changes nothing."""
    require_uv()
    with tempfile.TemporaryDirectory() as tmp:
        expected_path = Path(tmp) / 'ui-requirements.txt'
        _run_export(str(expected_path))
        expected = expected_path.read_text(encoding='utf-8').splitlines()

    actual = (NED / REQUIREMENTS).read_text(encoding='utf-8').splitlines()
    if actual == expected:
        print(f'ok: {REQUIREMENTS} matches uv.lock')
        return 0

    diff = difflib.unified_diff(
        actual,
        expected,
        fromfile=REQUIREMENTS,
        tofile='generated from uv.lock',
        lineterm='',
    )
    print('\n'.join(diff))
    print(
        f'\nerror: {REQUIREMENTS} does not match uv.lock.\n'
        '       Regenerate it with `python scripts/export_requirements.py` '
        'and commit the result\n'
        '       alongside pyproject.toml and uv.lock.'
    )
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        '--check',
        action='store_true',
        help='verify the committed file matches the lock without rewriting it',
    )
    args = ap.parse_args()

    if args.check:
        return check()

    regenerate()
    print(f'Wrote {REQUIREMENTS} from uv.lock.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
