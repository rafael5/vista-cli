"""Tests for output formatters (tsv, json)."""

import json

from vista_cli.format import json_out, tsv_out


class TestTsv:
    def test_header_and_row_emitted(self):
        rows = [{"a": "1", "b": "two"}]
        out = tsv_out.render_rows(rows, ["a", "b"])
        assert out == "a\tb\n1\ttwo\n"

    def test_missing_key_renders_empty(self):
        rows = [{"a": "1"}]
        out = tsv_out.render_rows(rows, ["a", "b"])
        assert out == "a\tb\n1\t\n"

    def test_tabs_and_newlines_replaced(self):
        rows = [{"a": "x\ty\nz"}]
        out = tsv_out.render_rows(rows, ["a"])
        assert out == "a\nx y z\n"

    def test_none_renders_empty(self):
        rows = [{"a": None}]
        out = tsv_out.render_rows(rows, ["a"])
        assert out == "a\n\n"

    def test_empty_list_emits_header_only(self):
        assert tsv_out.render_rows([], ["x"]) == "x\n"


class TestJson:
    def test_keys_sorted(self):
        out = json_out.render({"b": 1, "a": 2})
        parsed = json.loads(out)
        assert list(parsed.keys()) == ["a", "b"]

    def test_paths_serialized_as_strings(self):
        from pathlib import Path

        out = json_out.render({"path": Path("/tmp/foo")})
        assert "/tmp/foo" in out
