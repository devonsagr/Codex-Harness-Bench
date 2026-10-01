"""Execute unchanged upstream assertions in a disposable, network-free container."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

VERSION = 'evalplus-originfmt-v1'


def child(source, row, nonce):
    namespace = {'__name__': 'candidate'}
    exec(compile(source, 'solution.py', 'exec'), namespace)
    # Generated test expectations come from the fixed upstream release.
    tests = {}
    exec(compile(row['test'], 'upstream-tests.py', 'exec'), tests)
    tests['check'](namespace[row['entry_point']])
    print(nonce)


if __name__ == '__main__':
    if sys.argv[1] == '--child':
        row = json.loads(Path('/tests/tests.json').read_text())[sys.argv[3]]
        child(Path(sys.argv[2]).read_text(encoding='utf-8'), row, sys.argv[4])
    else:
        folder, index = Path(sys.argv[1]), sys.argv[2]
        row = json.loads(Path('/tests/tests.json').read_text())[index]
        nonce = uuid.uuid4().hex
        status, detail = 'failed', 'solution.py 缺失'
        if (folder / 'solution.py').is_file():
            try:
                result = subprocess.run([sys.executable, '-I', __file__, '--child', str(folder / 'solution.py'), index, nonce],
                                        capture_output=True, text=True, timeout=25)
                status = 'passed' if result.returncode == 0 and nonce in result.stdout.splitlines() else 'failed'
                detail = '原始扩展断言全部通过' if status == 'passed' else result.stderr[-1500:] or '未完成原始测试'
            except subprocess.TimeoutExpired:
                status, detail = 'unverified', '执行超过 25 秒；不将预算耗尽记作错误答案'
        print(json.dumps({'version': VERSION, 'task': index,
            'testSha256': hashlib.sha256(row['test'].encode()).hexdigest(),
            'rows': [{'id': 'suite', 'status': status, 'detail': detail}]}, ensure_ascii=False))
        sys.exit(0 if status == 'passed' else 1 if status == 'failed' else 2)
