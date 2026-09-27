"""Karar kriterleri, AHP matrisi ve ELECTRE eşik ayarları."""

import json
from pathlib import Path

import numpy as np


AVAILABLE_CRITERIA = {
    "fiyat", "efektif_guc", "guvenlik_puani",
    "akilli_ozellik_puani", "garanti_yil", "verimlilik",
}


def load_decision_config(path):
    """Kriter sırasını ve desteklenen ağırlık kaynağını doğrula."""
    path = Path(path)
    with path.open(encoding="utf-8") as file:
        config = json.load(file)
    criteria = config.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("Config içinde boş olmayan criteria listesi bulunmalıdır.")
    names = [item.get("name") for item in criteria]
    if len(set(names)) != len(names) or not set(names) <= AVAILABLE_CRITERIA:
        raise ValueError("Kriter adları benzersiz ve desteklenen sayısal alanlardan olmalıdır.")
    for item in criteria:
        if item.get("type") not in {"benefit", "cost"}:
            raise ValueError("Kriter tipi benefit veya cost olmalıdır.")
        if item.get("weight_source") != "ahp":
            raise ValueError("Şu anda yalnızca ahp ağırlık kaynağı desteklenir.")
    matrix_file = config.get("ahp_matrix_file")
    if not isinstance(matrix_file, str) or not matrix_file:
        raise ValueError("ahp_matrix_file tanımlanmalıdır.")
    thresholds = config.get("electre_thresholds", {"mode": "mean"})
    if thresholds.get("mode") not in {"mean", "fixed"}:
        raise ValueError("ELECTRE eşik modu mean veya fixed olmalıdır.")
    if thresholds["mode"] == "fixed":
        values = [thresholds.get("concordance"), thresholds.get("discordance")]
        if any(not isinstance(value, (int, float)) for value in values) or not np.isfinite(values).all() or any(
            not 0 <= value <= 1 for value in values
        ):
            raise ValueError("Sabit ELECTRE eşikleri 0–1 arasında olmalıdır.")
    config["electre_thresholds"] = thresholds
    config["matrix_path"] = str((path.parent / matrix_file).resolve())
    return config


def load_ahp_matrix(path, criterion_names):
    """Harici JSON matrisi ve kriter sırasını birlikte oku."""
    with Path(path).open(encoding="utf-8") as file:
        data = json.load(file)
    if data.get("criteria") != criterion_names:
        raise ValueError("AHP matrisindeki kriter sırası config ile aynı olmalıdır.")
    if "matrix" not in data:
        raise ValueError("AHP dosyasında matrix alanı eksik.")
    return data["matrix"], data.get("description", "")
