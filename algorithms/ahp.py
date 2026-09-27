"""Sütun normalizasyonu ve gerçek en büyük özdeğer ile AHP."""

import numpy as np


RANDOM_INDEX = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12,
                6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}
EIGEN_TOLERANCE = 1e-10


def calculate_ahp(matrix):
    """Ağırlıkları, lambda_max, CI, CR ve tutarlılık durumunu döndürür."""
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("AHP matrisi kare olmalıdır.")
    n = len(matrix)
    if n not in RANDOM_INDEX:
        raise ValueError("AHP matrisi 1–10 kriter içermelidir.")
    if not np.isfinite(matrix).all() or (matrix <= 0).any():
        raise ValueError("AHP değerleri sonlu ve pozitif olmalıdır.")
    if not np.allclose(np.diag(matrix), 1) or not np.allclose(matrix * matrix.T, 1):
        raise ValueError("Köşegen 1, karşılıklı değerler birbirinin tersi olmalıdır.")
    normalized = matrix / matrix.sum(axis=0)
    weights = normalized.mean(axis=1)
    # Pozitif karşılaştırma matrisinin Perron kökü gerçek ve en büyük özdeğerdir.
    lambda_max = float(np.max(np.linalg.eigvals(matrix).real))
    ci = (lambda_max - n) / (n - 1) if n > 1 else 0.0
    # Tam tutarlı matrislerde kayan nokta yuvarlaması λ_max'ı n'nin hemen
    # altına indirebilir; yalnızca bu sayısal gürültü sıfır kabul edilir.
    if -EIGEN_TOLERANCE <= ci < 0:
        ci = 0.0
    elif ci < 0:
        raise ArithmeticError("AHP tutarlılık indeksi beklenmedik biçimde negatif.")
    cr = ci / RANDOM_INDEX[n] if RANDOM_INDEX[n] > 0 else 0.0
    return {"normalized": normalized, "weights": weights,
            "lambda_max": lambda_max, "ci": ci, "cr": cr, "consistent": cr < 0.10}
