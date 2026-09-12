#!/bin/bash
set -euo pipefail
cat > /app/catalog.py <<'PY'
import csv
import json
import os
from pathlib import Path
import sys
import tempfile

from validation import normalize_sku, parse_quantity


def iter_products(source):
    reader = csv.reader(source, strict=True)
    try:
        header = next(reader, None)
        if not header:
            raise ValueError("missing header")
        header[0] = header[0].removeprefix("\ufeff")
        if len(header) != 3 or set(header) != {"sku", "name", "quantity"}:
            raise ValueError("expected sku,name,quantity header")
        seen = set()
        for fields in reader:
            if not fields:
                continue
            if len(fields) != 3:
                raise ValueError("wrong number of columns")
            row = dict(zip(header, fields))
            sku = normalize_sku(row["sku"])
            name = row["name"].strip()
            quantity = parse_quantity(row["quantity"])
            if not name or sku in seen:
                raise ValueError("empty name or duplicate SKU")
            seen.add(sku)
            yield {"sku": sku, "name": name, "quantity": quantity}
    except csv.Error as exc:
        raise ValueError(f"invalid CSV: {exc}") from exc


def import_catalog(source_path, destination_path):
    source_path, destination_path = Path(source_path), Path(destination_path)
    if source_path.resolve() == destination_path.resolve():
        raise ValueError("source and destination must differ")
    temporary = None
    try:
        with source_path.open(encoding="utf-8-sig", newline="") as source:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=destination_path.parent,
                                             prefix=".catalog-", suffix=".tmp", delete=False) as target:
                temporary = Path(target.name)
                count = 0
                for product in iter_products(source):
                    target.write(json.dumps(product, ensure_ascii=False) + "\n")
                    count += 1
            os.replace(temporary, destination_path)
            temporary = None
            return count
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m catalog source.csv catalog.jsonl", file=sys.stderr)
        return 2
    try:
        count = import_catalog(sys.argv[1], sys.argv[2])
    except (ValueError, OSError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 2
    print(f"Imported {count} products")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
cat > /app/README.md <<'MD'
# Catalog import

Run `python -m catalog source.csv catalog.jsonl`. The three columns sku,name,quantity may be reordered.
Input supports UTF-8 BOM, quoted commas and multiline fields. SKUs are normalized and unique; quantities are nonnegative integers.
Input is consumed incrementally. Output replaces the destination atomically only after all records validate; errors preserve the old file and remove temporary output. Source and destination must differ.
Successful CLI exits 0 with Imported N products. Data errors exit 2 and print to stderr.
Run `python -m unittest discover -s tests -v`. Standard library only.
MD
