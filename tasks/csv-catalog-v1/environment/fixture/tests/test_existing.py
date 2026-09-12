import io
from pathlib import Path
import tempfile
import unittest

from catalog import import_catalog, iter_products


class ExistingTests(unittest.TestCase):
    def test_simple_catalog(self):
        self.assertEqual(list(iter_products(io.StringIO("sku,name,quantity\na-1, Item ,2\n"))),
                         [{"sku": "A-1", "name": "Item", "quantity": 2}])

    def test_import_count(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "source.csv", Path(directory) / "out.jsonl"
            source.write_text("sku,name,quantity\nx,Name,0\n")
            self.assertEqual(import_catalog(source, target), 1)


if __name__ == "__main__":
    unittest.main()
