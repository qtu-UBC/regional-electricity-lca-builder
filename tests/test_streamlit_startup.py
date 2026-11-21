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
        database_selectors = [
            widget for widget in at.selectbox
            if widget.label == "Background LCI database (supported for openLCA export)"
        ]
        self.assertEqual(len(database_selectors), 1)
        self.assertEqual(
            list(database_selectors[0].options),
            ["ecoinvent 3.12, allocation cut-off"],
        )
        self.assertEqual(
            [tab.label for tab in at.tabs],
            ["1 · Build supply mix", "2 · Select providers",
             "3 · Export to openLCA", "Guide & cautions"],
        )
        self.assertFalse(any("GWP" in tab.label for tab in at.tabs))
        self.assertFalse(any(metric.label == "Life-cycle CI" for metric in at.metric))
        self.assertEqual(
            len([w for w in at.get("data_editor")]),
            1,
        )


if __name__ == "__main__":
    unittest.main()
