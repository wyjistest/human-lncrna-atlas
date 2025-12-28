import pytest


@pytest.mark.unit
def test_sanitize_csv_value_blocks_formula_injection_with_leading_whitespace_and_bom():
    from app.utils.streaming_export import sanitize_csv_value

    assert sanitize_csv_value("=1+1") == "'=1+1"
    assert sanitize_csv_value(" =1+1") == "' =1+1"
    assert sanitize_csv_value("\t=1+1") == "'\t=1+1"
    assert sanitize_csv_value("\ufeff=1+1") == "'\ufeff=1+1"
    assert sanitize_csv_value("normal") == "normal"
    assert sanitize_csv_value(123) == 123


@pytest.mark.unit
def test_sanitize_row_applies_to_all_string_fields():
    from app.utils.streaming_export import sanitize_row

    row = {"a": "=1+1", "b": " ok", "c": 1, "d": " +SUM(A1:A2)"}
    safe = sanitize_row(row)
    assert safe["a"] == "'=1+1"
    assert safe["b"] == " ok"
    assert safe["c"] == 1
    assert safe["d"] == "' +SUM(A1:A2)"

