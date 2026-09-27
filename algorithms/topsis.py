"""Fayda ve maliyet kriterlerini destekleyen TOPSIS."""

import numpy as np

from utils.helpers import prepare_matrix


def calculate_topsis(matrix, weights, directions):
    """Yakınlık skorlarını ve azalan skora göre satır indekslerini döndürür."""
    normalized, weighted, _ = prepare_matrix(matrix, weights, directions)
    benefit = np.array(directions) == "benefit"
    ideal_positive = np.where(benefit, weighted.max(axis=0), weighted.min(axis=0))
    ideal_negative = np.where(benefit, weighted.min(axis=0), weighted.max(axis=0))
    s_positive = np.linalg.norm(weighted - ideal_positive, axis=1)
    s_negative = np.linalg.norm(weighted - ideal_negative, axis=1)
    total = s_positive + s_negative
    # Tek alternatif veya tamamen aynı alternatifler için nötr skor.
    scores = np.divide(s_negative, total, out=np.full_like(total, 0.5), where=total > 0)
    ranking = np.argsort(-scores, kind="stable")
    return {"raw_matrix": np.asarray(matrix, dtype=float),
            "normalized": normalized, "weighted": weighted,
            "ideal_positive": ideal_positive, "ideal_negative": ideal_negative,
            "s_positive": s_positive, "s_negative": s_negative,
            "scores": scores, "ranking": ranking}
