import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(sys.argv.pop(1))
sys.path.insert(0, str(ROOT))
from catalog import import_catalog, iter_products


class CatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source.csv"
        self.target = self.root / "catalog.jsonl"

    def test_quoted_unicode_multiline_bom_reordered_crlf(self):
        text = '\ufeffquantity,name,sku\r\n2,"  螺丝,大号  ", a-1 \r\n0,"line one\r\nline two",B-2\r\n'
        self.assertEqual(list(iter_products(io.StringIO(text, newline=""))), [
            {"sku": "A-1", "name": "螺丝,大号", "quantity": 2},
            {"sku": "B-2", "name": "line one\r\nline two", "quantity": 0}])

    def test_streaming_before_later_rows(self):
        class Lines:
            def __init__(self): self.count = 0
            def __iter__(self): return self
            def __next__(self):
                self.count += 1
                if self.count == 1: return "sku,name,quantity\n"
                if self.count == 2: return "one,First,1\n"
                raise AssertionError("Consumed later rows before producing first product")
            def read(self, *args): raise AssertionError("read is not streaming")
            def readlines(self, *args): raise AssertionError("readlines is not streaming")
        source = Lines()
        products = iter_products(source)
        self.assertEqual(source.count, 0)
        self.assertEqual(next(products)["sku"], "ONE")
        self.assertEqual(source.count, 2)

    def test_bad_headers_and_empty_source(self):
        for text in ("", "sku,name\na,Name\n", "sku,name,quantity,extra\na,Name,1,x\n",
                     "sku,name,sku\na,Name,b\n", "name,quantity,unknown\nName,1,a\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                list(iter_products(io.StringIO(text)))

    def test_bad_rows_raise_value_error(self):
        for row in ("a,Name", "a,Name,1,extra", "a,,1", ",Name,1", "a,Name,-1", "a,Name,1.2",
                    "a,Name,", "a,Name,²", 'a,"unclosed,1', "a,Name,1\n A ,Other,2"):
            with self.subTest(row=row), self.assertRaises(ValueError):
                list(iter_products(io.StringIO("sku,name,quantity\n" + row)))

    def test_header_only_and_empty_lines(self):
        self.assertEqual(list(iter_products(io.StringIO("sku,name,quantity\n\n\r\n"))), [])
        self.assertEqual(len(list(iter_products(io.StringIO("sku,name,quantity\n\na,Name,1\n\n")))), 1)

    def test_atomic_failure_with_and_without_existing_destination(self):
        self.source.write_text("sku,name,quantity\na,Valid,1\nb,Bad,no\n")
        source_before = self.source.read_bytes()
        for existing in (True, False):
            if existing: self.target.write_bytes(b"keep exactly\r\n\x00")
            elif self.target.exists(): self.target.unlink()
            files_before = {p.name: p.read_bytes() for p in self.root.iterdir()}
            with self.assertRaises(ValueError): import_catalog(self.source, self.target)
            self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, files_before)
        self.assertEqual(self.source.read_bytes(), source_before)

    def test_atomic_success_order_and_no_temporary_files(self):
        self.source.write_text('\ufeffsku,name,quantity\na,"中文,引用",2\nb,Second,0\n', encoding="utf-8")
        before = self.source.read_bytes()
        self.target.write_text("old")
        self.assertEqual(import_catalog(self.source, self.target), 2)
        rows = [json.loads(line) for line in self.target.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows, [{"sku": "A", "name": "中文,引用", "quantity": 2}, {"sku": "B", "name": "Second", "quantity": 0}])
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["catalog.jsonl", "source.csv"])

    def test_same_path_keeps_source(self):
        self.source.write_text("sku,name,quantity\na,Name,1\n")
        before = self.source.read_bytes()
        with self.assertRaises(ValueError): import_catalog(self.source, self.source)
        self.assertEqual(self.source.read_bytes(), before)

    def test_success_does_not_open_destination_for_in_place_writing(self):
        self.source.write_text("sku,name,quantity\na,Name,1\n")
        self.target.write_text("old")
        writes, active = [], [True]
        target = os.path.abspath(self.target)
        def audit(event, args):
            if active[0] and event == "open" and isinstance(args[0], (str, bytes)):
                if os.path.abspath(os.fsdecode(args[0])) == target and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_TRUNC):
                    writes.append(args[2])
        sys.addaudithook(audit)
        try:
            import_catalog(self.source, self.target)
        finally:
            active[0] = False
        self.assertEqual(writes, [], "atomic replacement must not truncate/rewrite the live destination")

    def test_cli_success_and_data_error(self):
        self.source.write_text("sku,name,quantity\na,Name,1\n")
        cmd = [sys.executable, "-m", "catalog", str(self.source), str(self.target)]
        good = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertIn("Imported 1 products", good.stdout)
        before = self.target.read_bytes()
        self.source.write_text("sku,name,quantity\na,Name,1\na,Duplicate,2\n")
        bad = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(bad.returncode, 2)
        self.assertTrue(bad.stderr.strip())
        self.assertNotIn("Traceback", bad.stderr)
        self.assertEqual(self.target.read_bytes(), before)

    def test_contract_files_and_helper_reuse(self):
        for name, expected in json.loads(Path("/tests/protected.json").read_text()).items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)
        import validation
        wanted = {validation.normalize_sku.__code__, validation.parse_quantity.__code__}
        observed = set()
        def observe(frame, event, arg):
            if event == "call" and frame.f_code in wanted: observed.add(frame.f_code)
        previous = sys.getprofile()
        try:
            sys.setprofile(observe)
            list(iter_products(io.StringIO("sku,name,quantity\na,Name,1\n")))
        finally:
            sys.setprofile(previous)
        self.assertEqual(observed, wanted)

    def test_existing_tests(self):
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                                cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
