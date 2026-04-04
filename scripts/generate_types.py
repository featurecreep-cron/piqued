#!/usr/bin/env python3
"""Generate TypeScript interfaces from Pydantic v1 API schemas.

Reads all BaseModel subclasses from piqued.api.v1.schemas and emits
frontend/src/types/api.ts with matching TypeScript interfaces.

Usage:
    PYTHONPATH=. python scripts/generate_types.py              # writes to stdout
    PYTHONPATH=. python scripts/generate_types.py --write      # writes to frontend/src/types/api.ts
    PYTHONPATH=. python scripts/generate_types.py --check      # exits non-zero if file is stale
"""

from __future__ import annotations

import argparse
import inspect
import sys
import types
from pathlib import Path
from typing import get_args, get_origin

from pydantic import BaseModel

from piqued.api.v1 import schemas

# Map Python/Pydantic types to TypeScript types
_TS_MAP: dict[type, str] = {
    int: "number",
    float: "number",
    str: "string",
    bool: "boolean",
}


def _ts_type(annotation: type) -> str:
    """Convert a Python type annotation to a TypeScript type string."""
    origin = get_origin(annotation)
    args = get_args(annotation)

    # X | Y union syntax (types.UnionType in 3.10+)
    if isinstance(annotation, types.UnionType):
        non_none = [a for a in args if a is not type(None)]
        none_present = type(None) in args
        if len(non_none) == 1 and none_present:
            return f"{_ts_type(non_none[0])} | null"
        parts = [_ts_type(a) for a in args if a is not type(None)]
        result = " | ".join(parts)
        if none_present:
            result += " | null"
        return result

    # list[X]
    if origin is list:
        inner = _ts_type(args[0]) if args else "unknown"
        return f"{inner}[]"

    # dict[K, V]
    if origin is dict:
        key_t = _ts_type(args[0]) if args else "string"
        val_t = _ts_type(args[1]) if args else "unknown"
        return f"Record<{key_t}, {val_t}>"

    # Pydantic model reference — use the class name as the TS type
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation.__name__

    # datetime → string (ISO 8601 from JSON serialization)
    if hasattr(annotation, "__name__") and annotation.__name__ == "datetime":
        return "string"

    # Basic scalar types
    if annotation in _TS_MAP:
        return _TS_MAP[annotation]

    # NoneType
    if annotation is type(None):
        return "null"

    return "unknown"


def _generate_interface(model: type[BaseModel]) -> str:
    """Generate a TypeScript interface for a single Pydantic model."""
    lines = [f"export interface {model.__name__} {{"]
    for name, field_info in model.model_fields.items():
        annotation = model.__annotations__[name]
        ts = _ts_type(annotation)

        # Only mark as optional if the field has a non-required default
        # (e.g. `role: str = "user"`) but NOT nullable fields with None default
        optional = not field_info.is_required()

        opt = "?" if optional else ""

        lines.append(f"  {name}{opt}: {ts}")

    lines.append("}")
    return "\n".join(lines)


def generate() -> str:
    """Generate the full TypeScript types file."""
    header = (
        "// Auto-generated from piqued.api.v1.schemas — do not edit manually.\n"
        "// Regenerate with: PYTHONPATH=. python scripts/generate_types.py --write\n"
        "\n"
    )

    models: list[type[BaseModel]] = []
    for _name, obj in inspect.getmembers(schemas, inspect.isclass):
        if issubclass(obj, BaseModel) and obj is not BaseModel:
            models.append(obj)

    # Sort by source line order to match the Python file's organization
    models.sort(key=lambda m: inspect.getsourcelines(m)[1])

    interfaces = [_generate_interface(m) for m in models]
    return header + "\n\n".join(interfaces) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate TypeScript types from Pydantic schemas"
    )
    parser.add_argument(
        "--write", action="store_true", help="Write to frontend/src/types/api.ts"
    )
    parser.add_argument(
        "--check", action="store_true", help="Exit non-zero if file is stale"
    )
    args = parser.parse_args()

    output = generate()
    target = (
        Path(__file__).resolve().parent.parent / "frontend" / "src" / "types" / "api.ts"
    )

    if args.check:
        if not target.exists():
            print(f"FAIL: {target} does not exist", file=sys.stderr)
            sys.exit(1)
        existing = target.read_text()
        if existing != output:
            print(
                f"FAIL: {target} is stale — run: PYTHONPATH=. python scripts/generate_types.py --write",
                file=sys.stderr,
            )
            sys.exit(1)
        print("OK: types are up to date")
        sys.exit(0)

    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output)
        print(f"Wrote {target}")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
