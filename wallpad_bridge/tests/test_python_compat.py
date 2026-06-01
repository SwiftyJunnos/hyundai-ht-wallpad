import ast
import unittest
from pathlib import Path


class PythonCompatibilityTest(unittest.TestCase):
    def test_source_parses_on_python_312(self):
        source_files = Path("wallpad_bridge").glob("*.py")

        for source_file in source_files:
            with self.subTest(source_file=source_file):
                ast.parse(source_file.read_text(), filename=str(source_file), feature_version=(3, 12))
