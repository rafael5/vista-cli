"""Tests for the did_you_mean suggestion helper."""

from vista_cli.suggestions import did_you_mean


class TestDidYouMean:
    def test_typo_finds_close_match(self):
        candidates = ["PRCA45PT", "PRCAACT", "XUSCLEAN", "XPDUTL"]
        out = did_you_mean("PRCA45TP", candidates)
        assert "PRCA45PT" in out

    def test_returns_top_n(self):
        candidates = ["PRCA45PT", "PRCAACT", "PRCA45A", "PRCA45B"]
        out = did_you_mean("PRCA45", candidates, n=3)
        assert len(out) <= 3
        # All starting with PRCA45 should rank above PRCAACT
        assert "PRCA45PT" in out

    def test_ranked_by_similarity(self):
        candidates = ["PRCA45PT", "PRCAACT", "ZZZZZZZ"]
        out = did_you_mean("PRCA45TP", candidates)
        # PRCA45PT is a single-swap typo from PRCA45TP — should rank first
        assert out[0] == "PRCA45PT"

    def test_returns_empty_for_far_query(self):
        candidates = ["PRCA45PT", "PRCAACT"]
        out = did_you_mean("ZZZZZZZ", candidates)
        assert out == []

    def test_case_insensitive_match(self):
        candidates = ["PRCA45PT", "PRCAACT"]
        out = did_you_mean("prca45pt", candidates)
        # Lowercase input should still find the uppercase routine
        assert "PRCA45PT" in out

    def test_exact_match_returns_itself_first(self):
        candidates = ["PRCA45PT", "PRCAACT"]
        out = did_you_mean("PRCA45PT", candidates)
        assert out[0] == "PRCA45PT"

    def test_empty_candidates_returns_empty(self):
        assert did_you_mean("ANYTHING", []) == []

    def test_empty_query_returns_empty(self):
        assert did_you_mean("", ["PRCA45PT"]) == []

    def test_cutoff_filters_loose_matches(self):
        candidates = ["PRCA45PT"]
        # With strict cutoff, a 1-char overlap shouldn't match
        assert did_you_mean("Q", candidates, cutoff=0.9) == []
