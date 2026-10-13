import os
import tempfile
import unittest

from pipeline.cache import file_signature, signatures_match


class CacheSignatureTests(unittest.TestCase):
    def test_signature_detects_content_change(self):
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            path = handle.name
            handle.write(b"first")
        try:
            first = file_signature(path)
            with open(path, "wb") as handle:
                handle.write(b"second")
            second = file_signature(path)
            self.assertFalse(signatures_match(first, second))
            self.assertTrue(signatures_match(second, dict(second)))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
