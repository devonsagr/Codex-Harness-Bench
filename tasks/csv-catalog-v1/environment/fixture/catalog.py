import json
from pathlib import Path
import sys

from validation import normalize_sku, parse_quantity


def iter_products(source):
    next(source)
    for line in source:
        sku, name, quantity = line.strip().split(",")
        yield {"sku": normalize_sku(sku), "name": name.strip(), "quantity": parse_quantity(quantity)}


def import_catalog(source_path, destination_path):
    count = 0
    with Path(source_path).open(encoding="utf-8") as source, Path(destination_path).open("w", encoding="utf-8") as target:
        for product in iter_products(source):
            target.write(json.dumps(product, ensure_ascii=False) + "\n")
            count += 1
    return count


def main():
    count = import_catalog(sys.argv[1], sys.argv[2])
    print(f"Imported {count} products")


if __name__ == "__main__":
    main()
