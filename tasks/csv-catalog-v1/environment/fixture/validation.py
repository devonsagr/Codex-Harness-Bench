import re


def normalize_sku(value):
    if not isinstance(value, str):
        raise ValueError("SKU must be text")
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9-]+", value):
        raise ValueError("invalid SKU")
    return value


def parse_quantity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value.strip()):
        raise ValueError("quantity must be a nonnegative integer")
    return int(value.strip())
