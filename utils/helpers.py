"""CSV doğrulaması ve algoritmaların ortak matris işlemleri."""

from pathlib import Path

import numpy as np
import pandas as pd


COLUMNS = [
    "id", "marka", "model", "supports_single_phase", "supports_three_phase",
    "max_single_phase_kw", "max_three_phase_kw", "fiyat",
    "guvenlik_puani", "akilli_ozellik_puani", "garanti_yil", "verimlilik",
]


def load_stations(path: str | Path) -> pd.DataFrame:
    """Verimlilik 0–1, özellik puanları 0–10 aralığında olmalıdır."""
    data = pd.read_csv(path, dtype={"id": str})
    missing = set(COLUMNS) - set(data.columns)
    if missing:
        raise ValueError(f"CSV sütunları eksik: {', '.join(sorted(missing))}")
    data = data[COLUMNS].copy()
    if data.empty or data.isna().any().any():
        raise ValueError("CSV boş olamaz ve eksik değer içeremez.")
    for column in ["id", "marka", "model"]:
        data[column] = data[column].astype(str).str.strip()
        if data[column].eq("").any():
            raise ValueError(f"{column} boş olamaz.")
    if data["id"].duplicated().any():
        raise ValueError("İstasyon kimlikleri benzersiz olmalıdır.")
    for column in COLUMNS[3:]:
        data[column] = pd.to_numeric(data[column], errors="raise")
        if not np.isfinite(data[column]).all():
            raise ValueError(f"{column} sonlu sayılardan oluşmalıdır.")
    for flag, power in [("supports_single_phase", "max_single_phase_kw"),
                        ("supports_three_phase", "max_three_phase_kw")]:
        if not data[flag].isin([0, 1]).all():
            raise ValueError(f"{flag} yalnızca 0 veya 1 olabilir.")
        if ((data[flag] == 1) & (data[power] <= 0)).any() or (data[power] < 0).any():
            raise ValueError(f"{power} desteklenen fazda pozitif, diğer durumda negatif olamaz.")
        if ((data[flag] == 0) & (data[power] != 0)).any():
            raise ValueError(f"{power} desteklenmeyen fazda 0 olmalıdır.")
        data[flag] = data[flag].astype(bool)
    if not (data["supports_single_phase"] | data["supports_three_phase"]).all():
        raise ValueError("Her cihaz en az bir fazı desteklemelidir.")
    if (data["fiyat"] <= 0).any():
        raise ValueError("fiyat sıfırdan büyük olmalıdır.")
    for column in ["guvenlik_puani", "akilli_ozellik_puani"]:
        if not data[column].between(0, 10).all():
            raise ValueError(f"{column} 0–10 arasında olmalıdır.")
    if (data["garanti_yil"] < 0).any():
        raise ValueError("Garanti negatif olamaz.")
    if not ((data["verimlilik"] > 0) & (data["verimlilik"] <= 1)).all():
        raise ValueError("Verimlilik 0'dan büyük, 1'den küçük veya eşit olmalıdır.")
    return data


def prepare_matrix(matrix, weights, directions):
    """Karar matrisini doğrular ve sütunlarda vektör normalizasyonu yapar."""
    matrix = np.asarray(matrix, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if matrix.ndim != 2 or 0 in matrix.shape:
        raise ValueError("Karar matrisi boş olmayan iki boyutlu bir matris olmalıdır.")
    if weights.shape != (matrix.shape[1],) or len(directions) != matrix.shape[1]:
        raise ValueError("Kriter, ağırlık ve yön sayıları eşleşmelidir.")
    if not np.isfinite(matrix).all() or (matrix < 0).any():
        raise ValueError("Karar matrisi sonlu ve negatif olmayan sayılar içermelidir.")
    if not np.isfinite(weights).all() or (weights < 0).any() or weights.sum() <= 0:
        raise ValueError("Ağırlıklar negatif olamaz ve toplamları pozitif olmalıdır.")
    if any(direction not in ["cost", "benefit"] for direction in directions):
        raise ValueError("Kriter yönü cost veya benefit olmalıdır.")
    weights = weights / weights.sum()
    norms = np.linalg.norm(matrix, axis=0)
    normalized = np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)
    return normalized, normalized * weights, weights
