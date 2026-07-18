"""Golden Arabic fixtures — craft quality, not FakeProvider infrastructure."""

from app.generation.contracts.spoken_final_master import (
    strip_punctuation_from_spoken_body,
    validate_spoken_export_text,
)
from app.generation.egyptian_arabic_gate import run_egyptian_arabic_gate
from app.models.enums import AddressForm
from tests.golden.arabic_quality_fixtures import ACCEPTED, REJECTED


def test_rejected_fixtures_fail_gates():
    assert not run_egyptian_arabic_gate(REJECTED["banned_intro"]).ok
    assert not run_egyptian_arabic_gate(REJECTED["banned_outro"]).ok
    assert not run_egyptian_arabic_gate(REJECTED["literal_cold_audience"]).ok
    assert not run_egyptian_arabic_gate(REJECTED["colloquial_essay"]).ok
    assert not run_egyptian_arabic_gate(
        REJECTED["gender_switch"], address_form=AddressForm.MASCULINE
    ).ok
    punct = strip_punctuation_from_spoken_body(REJECTED["heavy_punctuation"])
    assert "،" not in punct and "؟" not in punct
    assert not validate_spoken_export_text("Hook: leak").ok


def test_accepted_fixtures_pass_arabic_gate():
    for key, text in ACCEPTED.items():
        report = run_egyptian_arabic_gate(text, address_form=AddressForm.MASCULINE)
        assert report.ok, (key, report.issues)
