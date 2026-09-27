"""ELECTRE I: uyum, uyumsuzluk ve yönlü üstünlük ilişkileri."""

import numpy as np

from utils.helpers import prepare_matrix


def calculate_electre(matrix, weights, directions, concordance_threshold=None,
                      discordance_threshold=None):
    """i → j ilişkisi: C(i,j) >= c ve D(i,j) <= d.

    Concordance kümesi i'nin j'den kötü olmadığı kriterlerdir.
    Discordance kümesi i'nin j'den kötü olduğu kriterlerdir.
    Uyumsuzluk, ağırlıklı matriste en büyük aleyhte farkın tüm
    kriterlerdeki en büyük mutlak farka oranı olarak hesaplanır.
    """
    normalized, weighted, weights = prepare_matrix(matrix, weights, directions)
    n = len(weighted)
    concordance = np.zeros((n, n))
    discordance = np.zeros((n, n))
    concordance_sets, discordance_sets = {}, {}
    signs = np.where(np.array(directions) == "benefit", 1, -1)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            difference = (weighted[i] - weighted[j]) * signs
            good = (difference >= 0) | np.isclose(difference, 0, atol=1e-12, rtol=0)
            bad = ~good
            concordance_sets[(i, j)] = np.flatnonzero(good).tolist()
            discordance_sets[(i, j)] = np.flatnonzero(bad).tolist()
            concordance[i, j] = weights[good].sum()
            absolute_difference = np.abs(weighted[i] - weighted[j])
            denominator = absolute_difference.max()
            if bad.any() and denominator > 0:
                discordance[i, j] = absolute_difference[bad].max() / denominator
    off_diagonal = ~np.eye(n, dtype=bool)
    # Tek alternatifte çift bulunmaz; eşikler üstünlük ilişkisi yaratmaz.
    if concordance_threshold is None:
        concordance_threshold = float(concordance[off_diagonal].mean()) if n > 1 else 1.0
    if discordance_threshold is None:
        discordance_threshold = float(discordance[off_diagonal].mean()) if n > 1 else 0.0
    if not np.isfinite([concordance_threshold, discordance_threshold]).all() or not (
        0 <= concordance_threshold <= 1 and 0 <= discordance_threshold <= 1
    ):
        raise ValueError("ELECTRE eşikleri 0–1 arasında sonlu değerler olmalıdır.")
    outranking = (concordance >= concordance_threshold) & (discordance <= discordance_threshold)
    np.fill_diagonal(outranking, False)
    return {"normalized": normalized, "weighted": weighted,
            "concordance_sets": concordance_sets, "discordance_sets": discordance_sets,
            "concordance": concordance, "discordance": discordance,
            "concordance_threshold": concordance_threshold,
            "discordance_threshold": discordance_threshold,
            "outranking": outranking, "outgoing": outranking.sum(axis=1),
            "incoming": outranking.sum(axis=0)}
