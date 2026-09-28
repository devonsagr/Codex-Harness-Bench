def decode_event(event):
    if 'kind' not in event or 'amount' not in event:
        raise ValueError('missing event fields')
    return {'kind': event['kind'], 'amount': float(event['amount'])}
