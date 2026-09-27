"""Çalıştırma: python -m unittest discover -s tests -v"""

import unittest
from pathlib import Path

import numpy as np

from algorithms.ahp import calculate_ahp
from algorithms.electre import calculate_electre
from algorithms.filter import filter_stations
from algorithms.topsis import calculate_topsis
from utils.helpers import load_stations


class AlgorithmTests(unittest.TestCase):
    def test_ahp_known_weights(self):
        weights = np.array([0.5, 0.3, 0.2])
        result = calculate_ahp(weights[:, None] / weights[None, :])
        np.testing.assert_allclose(result["weights"], weights)
        self.assertAlmostEqual(result["lambda_max"], 3)
        self.assertAlmostEqual(result["cr"], 0)
        self.assertTrue(result["consistent"])

    def test_ahp_inconsistent_and_invalid(self):
        result = calculate_ahp([[1, 9, 1/9], [1/9, 1, 9], [9, 1/9, 1]])
        self.assertFalse(result["consistent"])
        with self.assertRaises(ValueError):
            calculate_ahp([[1, 3], [3, 1]])

    def test_topsis_dominant_alternative(self):
        result = calculate_topsis([[10, 9], [20, 3]], [0.5, 0.5], ["cost", "benefit"])
        np.testing.assert_allclose(result["scores"], [1, 0])
        self.assertEqual(result["ranking"].tolist(), [0, 1])

    def test_topsis_identical_single_and_zero_column(self):
        for matrix in [[[10, 0]], [[10, 0], [10, 0]]]:
            result = calculate_topsis(matrix, [0.5, 0.5], ["cost", "benefit"])
            np.testing.assert_allclose(result["scores"], 0.5)

    def test_electre_dominance(self):
        result = calculate_electre([[10, 9], [20, 3]], [0.5, 0.5], ["cost", "benefit"])
        self.assertTrue(result["outranking"][0, 1])
        self.assertFalse(result["outranking"][1, 0])
        self.assertEqual(result["concordance_sets"][(0, 1)], [0, 1])
        self.assertEqual(result["discordance_sets"][(1, 0)], [0, 1])
        self.assertEqual(result["discordance"][1, 0], 1)

    def test_electre_identical(self):
        result = calculate_electre([[1, 2], [1, 2]], [0.5, 0.5], ["cost", "benefit"])
        self.assertEqual(result["discordance"].sum(), 0)
        self.assertFalse(result["outranking"][0, 0])
        self.assertTrue(result["outranking"][0, 1])

    def test_filter_budget_phase_and_energy(self):
        stations = load_stations(Path(__file__).resolve().parents[1] / "data/sarj_istasyonlari.csv")
        suitable, excluded = filter_stations(stations, 50, 11, 60, 18, "monofaz", 7.4, 19000)
        self.assertEqual(suitable["id"].tolist(), ["S01", "S02", "S04"])
        self.assertEqual(len(excluded), 7)
        np.testing.assert_allclose(suitable["gunluk_enerji"], 9)
        self.assertAlmostEqual(suitable.iloc[1]["sarj_suresi"], 9 / 7.4)
        empty, _ = filter_stations(stations, 0, 11, 60, 18, "trifaz", 7.4, 1)
        self.assertTrue(empty.empty)


if __name__ == "__main__":
    unittest.main()
