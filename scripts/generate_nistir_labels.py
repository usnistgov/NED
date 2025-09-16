#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable


# Hardcoded paths relative to this file's repository root
REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = REPO_ROOT / "resources" / "data" / "nistir.json"
OUTPUT_PATH = REPO_ROOT / "ned_app" / "schemas" / "nistir_labels.json"

CHILD_KEYS: tuple[str, ...] = ("group_elements", "indiv_elements", "sub_elements")


def transform_id(compact_id: str) -> str:
    """
    Transform compact NISTIR IDs like "A1011" into dotted notation like "A.10.1.1".

    Rules:
    - Letter prefix retained as-is (e.g., "A").
    - If numeric part length <= 2 → append as a single segment (e.g., "A10" → "A.10").
    - If numeric part length > 2 → first two digits form one segment, remaining digits
      form subsequent single-digit segments. Trailing zeros in the remaining digits
      are trimmed (e.g., "A1010" → "A.10.1").
    """
    # If it's just letters (e.g., "A", "B"), return as-is
    if compact_id.isalpha():
        return compact_id

    if not compact_id:
        raise ValueError("Empty ID encountered")

    prefix = compact_id[0]
    digits = compact_id[1:]

    if not prefix.isalpha() or not digits.isdigit():
        # Fall back to returning the compact_id unchanged if format is unexpected
        return compact_id

    parts: list[str] = [prefix]

    if len(digits) <= 2:
        # Single numeric segment
        parts.append(str(int(digits)))  # normalize leading zeros if any
    else:
        # First two digits as the first numeric segment
        first_two = digits[:2]
        parts.append(str(int(first_two)))
        rest = list(digits[2:])

        # Trim trailing zeros from the rest
        while rest and rest[-1] == "0":
            rest.pop()

        # Each remaining digit becomes its own segment
        for d in rest:
            parts.append(str(int(d)))  # normalize to no leading zeros

    return ".".join(parts)


def _iter_children(node: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for key in CHILD_KEYS:
        children = node.get(key)
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    yield child


def build_label_map(data: Any) -> Dict[str, str]:
    """Traverse the nested NISTIR structure and build a flat id→name map."""
    labels: Dict[str, str] = {}

    def visit(node: dict[str, Any]) -> None:
        cid = node.get("id")
        name = node.get("name")
        if isinstance(cid, str) and isinstance(name, str):
            tid = transform_id(cid)
            labels[tid] = name
        for child in _iter_children(node):
            visit(child)

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                visit(item)
    elif isinstance(data, dict):
        visit(data)
    else:
        raise ValueError("Unexpected JSON structure for NISTIR data: expected list or dict root")

    return labels


def main() -> None:
    with INPUT_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    labels = build_label_map(data)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(labels, f, indent=2, ensure_ascii=False)
        f.write("\n")  # newline at end of file


if __name__ == "__main__":
    main()
