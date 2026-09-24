"""
Unit tests for Module 8 multi-source hypothesis testing.
"""

from src.ranking.hypotheses import test_hypotheses as run_hypotheses_test, to_hypothesis_posteriors


def test_hypotheses_single_source_scenario():
    """Construct a single-source scenario (H1 preferred)."""
    single_source_data = {
        "one_source": {
            "bic": 120.0,
            "iou": 0.65,
        },
        "two_source": {
            "bic": 190.0,
            "iou": 0.30,
        },
    }

    report = run_hypotheses_test("case_single", spillsplit_data=single_source_data)
    assert report.preferred_hypothesis_id == "H1"
    h1 = next(h for h in report.hypotheses if h.id == "H1")
    h2 = next(h for h in report.hypotheses if h.id == "H2")
    assert h1.posterior > h2.posterior
    assert h1.status == "TESTABLE"
    assert h2.status == "TESTABLE"

    # H3-H5 should be INSUFFICIENT_DATA
    for hid in ["H3", "H4", "H5"]:
        item = next(h for h in report.hypotheses if h.id == hid)
        assert item.status == "INSUFFICIENT_DATA"
        assert item.posterior == 0.0


def test_hypotheses_two_source_scenario():
    """Construct a two-source scenario (H2 preferred)."""
    two_source_data = {
        "one_source": {
            "bic": 240.0,
            "iou": 0.15,
        },
        "two_source": {
            "bic": 110.0,
            "iou": 0.72,
        },
    }

    report = run_hypotheses_test("case_multi", spillsplit_data=two_source_data)
    assert report.preferred_hypothesis_id == "H2"
    h1 = next(h for h in report.hypotheses if h.id == "H1")
    h2 = next(h for h in report.hypotheses if h.id == "H2")
    assert h2.posterior > h1.posterior


def test_hypotheses_missing_data():
    """Verify behavior when data is unavailable."""
    report = run_hypotheses_test("nonexistent_case_999", spillsplit_data=None)
    assert report.preferred_hypothesis_id == "INSUFFICIENT_DATA"
    assert all(h.status == "INSUFFICIENT_DATA" for h in report.hypotheses)

    posteriors = to_hypothesis_posteriors(report)
    assert len(posteriors) == 5
