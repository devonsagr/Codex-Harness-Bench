def make_rows(n):
    return [{'group': 'G' + str(i % 20), 'value': None if i % 17 == 0 else i % 7} for i in range(n)]
