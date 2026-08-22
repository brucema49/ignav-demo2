"""Regression tests for the RTDTC-GPS evaluation helpers."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).resolve().parents[1] / "a-cpt" / "plot" / "error_rtdtc.py"
SPEC = importlib.util.spec_from_file_location("error_rtdtc", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
EVALUATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVALUATOR)


def test_primary_mask_prefers_tightly_coupled_update_epochs() -> None:
    mask, source = EVALUATOR.primary_statistics_mask(np.array([0, 2, 3, 8, 8, -1]))

    assert source == "Qins=8 (tightly coupled update)"
    assert mask.tolist() == [False, False, False, True, True, False]


def test_integer_second_mask_selects_nearest_unique_epoch() -> None:
    mask = EVALUATOR.integer_second_mask(np.array([10.01, 10.49, 10.51, 11.02, 11.49]))

    assert mask.tolist() == [True, False, False, True, False]


def test_primary_mask_uses_loosely_coupled_updates_when_tc_is_absent() -> None:
    mask, source = EVALUATOR.primary_statistics_mask(np.array([0, 2, 3, 3, -1]))

    assert source == "Qins=3"
    assert mask.tolist() == [False, False, True, True, False]


def test_primary_mask_falls_back_to_all_epochs_without_qins_metadata() -> None:
    mask, source = EVALUATOR.primary_statistics_mask(np.array([-1, -1]))

    assert source == "all valid epochs (Qins unavailable)"
    assert mask.tolist() == [True, True]


def test_accuracy_diagnosis_distinguishes_missing_updates_from_drift() -> None:
    missing = EVALUATOR.classify_accuracy(
        horizontal_rmse=12.0,
        qins_counts={0: 0, 2: 980, 3: 0, 8: 20, 11: 0, -1: 0},
        propagation_rmse=14.0,
    )
    drift = EVALUATOR.classify_accuracy(
        horizontal_rmse=12.0,
        qins_counts={0: 0, 2: 200, 3: 0, 8: 800, 11: 0, -1: 0},
        propagation_rmse=3.0,
    )

    assert missing["category"] == "insufficient_gnss_updates"
    assert drift["category"] == "noisy_or_misaligned_updates"


def test_accuracy_diagnosis_uses_qins11_only_at_integer_update_points() -> None:
    result = EVALUATOR.classify_accuracy(
        horizontal_rmse=390.0,
        qins_counts={0: 0, 2: 9900, 3: 0, 8: 47, 11: 53, -1: 0},
        propagation_rmse=389.0,
        primary_count=101,
        total_count=10000,
        primary_qins11_count=53,
    )

    assert result["category"] == "insufficient_gnss_updates"


def test_summary_record_contains_primary_and_all_epoch_metrics() -> None:
    record = EVALUATOR.build_summary_record(
        label="ignav-RTDTC-GPS",
        primary_stats={"e": {"rmse": 1.0}, "n": {"rmse": 2.0}, "u": {"rmse": 3.0},
                       "hor": {"rmse": 2.24}, "threeD": {"rmse": 3.74}},
        all_stats={"hor": {"rmse": 4.0}},
        qins_counts={0: 1, 2: 2, 3: 0, 8: 3, 11: 1, -1: 0},
        primary_source="Qins=8",
        diagnosis={"category": "nominal", "recommendation": "keep baseline"},
    )

    assert record["primary_source"] == "Qins=8"
    assert record["horizontal_rmse_m"] == 2.24
    assert record["all_epoch_horizontal_rmse_m"] == 4.0
    assert record["qins8_count"] == 3
