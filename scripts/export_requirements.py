#!/usr/bin/env python
"""Generate the front-end's pinned ``requirements.txt`` from ``uv.lock``.

The front-end deployment repo installs the UI with plain pip, so it needs a
pinned ``requirements.txt`` rather than a lock file. That file is generated,
never hand-edited, and never committed to NED: ``uv.lock`` is the only
dependency record here, and this module owns the one command that derives the
pip file from it.

Two callers share it, so the flags cannot drift apart between them:

    * ``scripts/export_frontend.py``, which writes the file straight into the
      front-end repo when publishing.
    * Maintainers who want the pins for a pip-based environment.

Usage (run from anywhere; the lock is resolved relative to this file):

    python scripts/export_requirements.py               # print to stdout
    python scripts/export_requirements.py -o reqs.txt   # write to a file
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

NED = Path(__file__).resolve().parent.parent


def export_cmd(dest: Path | None = None) -> list[str]:
    """The uv invocation that exports the pinned requirements.

    Writes to ``dest`` when given, otherwise to stdout. ``--locked`` refuses a
    lock that is out of date with pyproject.toml, so a stale pin can never be
    published. The remaining flags strip everything that is not a pinned
    requirement, because pip is the only consumer.
    """
    cmd = [
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
    ]
    if dest is not None:
        cmd += ['-o', str(dest)]
    return cmd


def require_uv() -> None:
    """Exit with a clear message if uv is not available."""
    if shutil.which('uv') is None:
        sys.exit('error: uv is not on PATH; it is needed to export requirements')


def _run_export(dest: Path | None) -> None:
    cmd = export_cmd(dest)
    # stderr, so that printing to stdout yields nothing but the requirements.
    print('+', ' '.join(cmd), file=sys.stderr)
    try:
        # uv echoes the requirements to stdout even when writing them to dest;
        # silence that echo so a file export does not also dump the file.
        subprocess.run(
            cmd,
            cwd=NED,
            check=True,
            stdout=subprocess.DEVNULL if dest is not None else None,
        )
    except subprocess.CalledProcessError as exc:
        sys.exit(f'error: uv export failed with exit status {exc.returncode}')


def regenerate(dest: Path | None = None) -> None:
    """Export the pinned requirements from the lock to ``dest`` (or stdout)."""
    require_uv()
    _run_export(dest)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        '-o',
        '--output',
        type=Path,
        help='file to write the requirements to (default: stdout)',
    )
    args = ap.parse_args()

    dest = args.output.resolve() if args.output else None
    regenerate(dest)
    if dest is not None:
        print(f'Wrote {dest} from uv.lock.', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
