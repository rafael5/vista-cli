"""Tests for canonical package id resolution.

vista-meta names packages by directory ("Outpatient Pharmacy");
vista-docs names them by VDL app_code ("PSO") AND VistA namespace
("PSO" — sometimes overlapping but not always). canonical.py owns
the bidirectional map.
"""

from vista_cli.canonical import (
    PackageId,
    classify_ref,
    resolve_package,
)


class TestResolvePackage:
    def test_directory_form_resolves(self):
        pkg = resolve_package("Outpatient Pharmacy")
        assert pkg.directory == "Outpatient Pharmacy"
        assert pkg.ns == "PSO"
        assert pkg.app_code == "PSO"

    def test_namespace_resolves(self):
        pkg = resolve_package("PSO")
        assert pkg.directory == "Outpatient Pharmacy"
        assert pkg.ns == "PSO"

    def test_kernel_directory(self):
        pkg = resolve_package("Kernel")
        assert pkg.ns == "XU"

    def test_kernel_ns(self):
        pkg = resolve_package("XU")
        assert pkg.directory == "Kernel"

    def test_case_insensitive_ns(self):
        # Namespace lookup is case-insensitive
        pkg = resolve_package("pso")
        assert pkg.ns == "PSO"

    def test_unknown_returns_none(self):
        assert resolve_package("ZZZNOTAPACKAGE") is None


class TestClassifyRef:
    def test_routine_only(self):
        assert classify_ref("PRCA45PT") == ("routine", "PRCA45PT", None)

    def test_tag_at_routine(self):
        assert classify_ref("EN^XUSCLEAN") == ("routine", "XUSCLEAN", "EN")

    def test_caret_routine(self):
        assert classify_ref("^XUSCLEAN") == ("routine", "XUSCLEAN", None)

    def test_global_with_subscript(self):
        kind, name, _ = classify_ref("^DPT(123,0)")
        assert kind == "global"
        assert name == "DPT"

    def test_global_root_only(self):
        kind, name, _ = classify_ref("^DPT")
        # Ambiguous — could be global or routine. We default to routine
        # because routines.tsv membership is the tiebreaker; the caller
        # disambiguates.
        assert kind == "routine"
        assert name == "DPT"

    def test_file_number(self):
        kind, name, _ = classify_ref("9.8")
        assert kind == "file"
        assert name == "9.8"

    def test_integer_file_number(self):
        kind, name, _ = classify_ref("200")
        assert kind == "file"

    def test_patch_id(self):
        kind, name, _ = classify_ref("PRCA*4.5*341")
        assert kind == "patch"
        assert name == "PRCA*4.5*341"

    def test_lowercase_identifier_is_routine(self):
        # FileMan calls it ROUTINE, but ; ;\n etc. — all uppercase
        # in VistA. Lowercase still classifies as routine for safety.
        kind, name, _ = classify_ref("xyz")
        assert kind == "routine"


class TestPackageId:
    def test_repr_round_trips(self):
        pkg = PackageId(directory="Kernel", ns="XU", app_code="XU")
        assert "Kernel" in repr(pkg)
        assert "XU" in repr(pkg)
