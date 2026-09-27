"""Karar motorunun matematiksel ve akış testleri: python -m pytest -q."""

import json
from pathlib import Path

import numpy as np
import pytest

from algorithms.ahp import calculate_ahp
from algorithms.electre import calculate_electre
from algorithms.filter import add_derived_values, filter_stations
from algorithms.topsis import calculate_topsis
from decision_engine import (
    DEFAULT_CONFIG, DEFAULT_STATIONS, InconsistentAHPError,
    detect_method_disagreement, run_decision,
)
from utils.decision_config import load_decision_config
from utils.helpers import load_stations


@pytest.fixture
def inputs():
    return {"daily_km": 50, "vehicle_ac_kw": 11, "battery_kwh": 60,
            "consumption": 18, "home_phase": "monofaz", "home_max_kw": 7.4,
            "budget": 30000}


def test_ahp_reciprocal_diagonal_square_positive():
    for bad in [
        [[1, 2, 3], [0.5, 1, 2]],
        [[2, 3], [1 / 3, 1]],
        [[1, 3], [3, 1]],
        [[1, -1], [-1, 1]],
    ]:
        with pytest.raises(ValueError):
            calculate_ahp(bad)


def test_ahp_weights_sum_and_true_eigenvalue():
    matrix = np.array([[1, 4, 7], [1 / 4, 1, 3], [1 / 7, 1 / 3, 1]])
    result = calculate_ahp(matrix)
    assert sum(result["weights"]) == pytest.approx(1)
    assert result["lambda_max"] == pytest.approx(max(np.linalg.eigvals(matrix).real))
    ratio_mean = np.mean((matrix @ result["weights"]) / result["weights"])
    assert abs(result["lambda_max"] - ratio_mean) > 1e-5
    assert result["ci"] == pytest.approx((result["lambda_max"] - 3) / 2)
    assert result["cr"] == pytest.approx(result["ci"] / 0.58)


def test_ahp_consistency_and_reject_in_main_flow(tmp_path, inputs):
    matrix = np.ones((6, 6))
    matrix[0, 1], matrix[1, 0] = 9, 1 / 9
    matrix[1, 2], matrix[2, 1] = 9, 1 / 9
    matrix[0, 2], matrix[2, 0] = 1 / 9, 9
    assert calculate_ahp(np.ones((6, 6)))["consistent"]
    result = calculate_ahp(matrix)
    assert result["cr"] >= 0.10
    matrix_data = json.loads((DEFAULT_CONFIG.parent.parent / "data/ahp_ornek_matris.json").read_text(encoding="utf-8"))
    matrix_data["matrix"] = matrix.tolist()
    file = tmp_path / "inconsistent.json"
    file.write_text(json.dumps(matrix_data), encoding="utf-8")
    with pytest.raises(InconsistentAHPError, match="CR="):
        run_decision(inputs, matrix_path=file)


def test_external_ahp_file_is_labeled_example(inputs):
    config = load_decision_config(DEFAULT_CONFIG)
    result = run_decision(inputs)
    assert Path(config["matrix_path"]).is_file()
    assert "örnek" in result["ahp_matrix_description"].lower()
    assert result["ahp_weights"]["fiyat"] > result["ahp_weights"]["garanti_yil"]


def test_topsis_cost_benefit_and_score_bounds():
    result = calculate_topsis([[10, 9], [20, 3], [15, 6]],
                              [0.5, 0.5], ["cost", "benefit"])
    assert result["ideal_positive"][0] == min(result["weighted"][:, 0])
    assert result["ideal_positive"][1] == max(result["weighted"][:, 1])
    assert result["ideal_negative"][0] == max(result["weighted"][:, 0])
    assert result["ranking"].tolist() == [0, 2, 1]
    assert np.all((result["scores"] >= 0) & (result["scores"] <= 1))
    np.testing.assert_allclose(result["scores"], [1, 0, 0.5], atol=0.1)


def test_phase_capacities_and_effective_power():
    stations = load_stations(DEFAULT_STATIONS)
    mono, _ = filter_stations(stations, "monofaz", 30000)
    tri, _ = filter_stations(stations, "trifaz", 30000)
    assert mono.set_index("id").loc["S06", "istasyon_kullanilabilir_guc"] == 3.7
    assert tri.set_index("id").loc["S06", "istasyon_kullanilabilir_guc"] == 11
    assert "S07" not in mono["id"].tolist()
    mono_derived = add_derived_values(mono, 50, 22, 60, 18, 22)
    tri_derived = add_derived_values(tri, 50, 22, 60, 18, 7.4)
    assert mono_derived.set_index("id").loc["S06", "efektif_guc"] == 3.7
    assert tri_derived.set_index("id").loc["S06", "efektif_guc"] == 7.4
    assert mono_derived.set_index("id").loc["S06", "gunluk_enerji"] == 9
    assert mono_derived.set_index("id").loc["S06", "sarj_suresi"] == pytest.approx(9 / 3.7)


def test_incompatible_alternative_never_enters_topsis(inputs):
    result = run_decision(inputs)
    eligible = [row["id"] for row in result["filtered_alternatives"]]
    assert "S07" not in eligible
    assert any(row["id"] == "S07" and "Ev fazını desteklemiyor" in row["reasons"]
               for row in result["exclusions"])
    assert len(result["topsis"]["raw_matrix"]) == len(eligible)
    assert set(result["topsis"]["rank"]) == set(eligible)


def test_electre_sets_mean_threshold_and_diagonal():
    result = calculate_electre([[10, 9], [20, 3], [15, 6]],
                               [0.5, 0.5], ["cost", "benefit"])
    mask = ~np.eye(3, dtype=bool)
    assert not np.diag(result["outranking"]).any()
    assert result["concordance_threshold"] == pytest.approx(result["concordance"][mask].mean())
    assert result["discordance_threshold"] == pytest.approx(result["discordance"][mask].mean())
    assert result["concordance_sets"][(0, 1)] == [0, 1]
    assert result["discordance_sets"][(1, 0)] == [0, 1]
    assert result["concordance"][0, 1] == pytest.approx(1)
    assert result["discordance"][0, 1] == pytest.approx(0)
    assert result["concordance"][1, 0] == pytest.approx(0)
    assert result["discordance"][1, 0] == pytest.approx(1)


def test_electre_fixed_threshold_config(tmp_path, inputs):
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config["ahp_matrix_file"] = str((DEFAULT_CONFIG.parent.parent / "data/ahp_ornek_matris.json").resolve())
    config["electre_thresholds"] = {"mode": "fixed", "concordance": 0.7, "discordance": 0.2}
    file = tmp_path / "config.json"
    file.write_text(json.dumps(config), encoding="utf-8")
    result = run_decision(inputs, config_path=file)
    assert result["electre"]["concordance_threshold"] == 0.7
    assert result["electre"]["discordance_threshold"] == 0.2


def test_method_disagreement_only_for_one_way_opposition():
    ranking = [0, 1, 2]
    no_relation = np.zeros((3, 3), dtype=bool)
    assert detect_method_disagreement(ranking, no_relation) == []
    no_relation[1, 0] = True
    assert detect_method_disagreement(ranking, no_relation) == [1]
    no_relation[0, 1] = True
    assert detect_method_disagreement(ranking, no_relation) == []


def test_method_disagreement_in_complete_decision_flow(tmp_path, inputs):
    """TOPSIS birincisi kalır; ELECTRE karşıtlığı açıklamada yer alır."""
    stations = load_stations(DEFAULT_STATIONS).iloc[:4].copy()
    stations["fiyat"] = [3, 11, 7, 1]
    stations["guvenlik_puani"] = [7.5, 7, 4, 7.5]
    stations["akilli_ozellik_puani"] = [2.5, 6.5, 5, 1]
    stations_file = tmp_path / "stations.csv"
    stations.to_csv(stations_file, index=False)
    criteria = ["fiyat", "guvenlik_puani", "akilli_ozellik_puani"]
    priorities = np.array([8, 7, 5], dtype=float)
    matrix_file = tmp_path / "ahp.json"
    matrix_file.write_text(json.dumps({"criteria": criteria,
                                       "matrix": (priorities[:, None] / priorities[None, :]).tolist()}),
                           encoding="utf-8")
    config = {"criteria": [{"name": name, "type": direction, "weight_source": "ahp"}
                           for name, direction in zip(criteria, ["cost", "benefit", "benefit"])],
              "ahp_matrix_file": "ahp.json", "electre_thresholds": {"mode": "mean"}}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config), encoding="utf-8")
    result = run_decision(inputs, stations_file, config_file)
    assert result["final_ranking"][0]["id"] == "S01"
    assert result["method_disagreement"] is True
    assert result["disagreeing_alternatives"] == ["S04"]
    assert any("Yöntemler arasında farklılık bulunmaktadır" in line
               for line in result["explanation"])


def test_all_alternatives_filtered_returns_audit_without_mcdm(inputs):
    inputs["budget"] = 1
    result = run_decision(inputs)
    assert result["status"] == "no_alternatives"
    assert result["filtered_alternatives"] == []
    assert len(result["exclusions"]) == 10
    assert result["topsis"] is None
    assert result["electre"] is None
    assert result["final_ranking"] == []


def test_audit_is_single_json_serializable_result(inputs):
    result = run_decision(inputs)
    assert json.loads(json.dumps(result)) == result
    assert result["final_ranking"][0]["id"] == result["topsis"]["rank"][0]
    assert all(0 <= score <= 1 for score in result["topsis"]["C_star"])
    assert len(result["electre"]["concordance_sets"]) == len(result["filtered_alternatives"]) * (len(result["filtered_alternatives"]) - 1)
    assert "teorik" in " ".join(result["explanation"])
