def summarize(rows):
    names = sorted({row['group'] for row in rows})
    return {name: sum(row.get('value') or 0 for row in rows if row['group'] == name) for name in names}
