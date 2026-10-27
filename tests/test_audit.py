from sinhala_corpus.audit import audit_layout


def test_paired_numbers_flag_possible_merged_columns():
    report = audit_layout("31     39\nleft verse\tright verse\n")

    assert report["layout_status"] == "requires_review"
    assert report["multiple_number_lines"] == [{"line": 1, "numbers": [31, 39]}]
    assert "possible_merged_columns" in report["quality_flags"]


def test_single_numbers_do_not_trigger_column_flag():
    report = audit_layout("1\nFirst verse\n\n2\nSecond verse")

    assert report["single_number_line_count"] == 2
    assert report["multiple_number_line_count"] == 0
    assert report["layout_status"] == "not_flagged"


def test_numbers_inside_text_are_not_number_markers():
    report = audit_layout("Written in 2023\nVerse 31 and 39\n")

    assert report["single_number_line_count"] == 0
    assert report["multiple_number_line_count"] == 0
