def total(rows, sku):
    return sum(int(row['quantity']) for row in rows if row['sku'] == sku)
