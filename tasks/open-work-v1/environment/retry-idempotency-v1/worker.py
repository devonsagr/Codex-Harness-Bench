ledger = {}

def handle(job):
    account = job['account']
    ledger[account] = ledger.get(account, 0) - job['amount']
    return {'status': 'done', 'job_id': job['id']}
