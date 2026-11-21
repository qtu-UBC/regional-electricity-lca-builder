"""Smoke test the actual Streamlit entrypoint, not just individual modules."""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest


class StreamlitStartupTests(unittest.TestCase):
    def test_provider_import_symbols(self):
        from provider_library import (
            library_errors, approved_candidates, approved_markets,
            catalog_for_selection, ranked_candidates, provider_class,
            region_preference,
        )
        self.assertTrue(all(callable(obj) for obj in (
            library_errors, approved_candidates, approved_markets,
            catalog_for_selection, ranked_candidates, provider_class,
            region_preference,
        )))

    def test_app_starts_without_catalog(self):
        root = Path(__file__).resolve().parents[1]
        at = AppTest.from_file(root / "app.py", default_timeout=20)
        at.run()
        self.assertFalse(at.exception, [
            getattr(item, "message", repr(item)) for item in at.exception
        ])


if __name__ == "__main__":
    unittest.main()
