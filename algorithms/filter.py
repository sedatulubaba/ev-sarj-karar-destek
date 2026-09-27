"""Faza bağlı teknik uygunluk ve kullanıcıya özgü enerji hesapları."""

import numpy as np


PHASE_COLUMNS = {
    "monofaz": ("supports_single_phase", "max_single_phase_kw"),
    "trifaz": ("supports_three_phase", "max_three_phase_kw"),
}


def filter_stations(stations, home_phase, budget):
    """Bütçe ve desteklenen faza göre ayır; fazdaki kullanılabilir gücü ekle."""
    if home_phase not in PHASE_COLUMNS:
        raise ValueError("Ev fazı monofaz veya trifaz olmalıdır.")
    if not np.isfinite(budget) or budget <= 0:
        raise ValueError("Bütçe pozitif ve sonlu olmalıdır.")
    support_column, power_column = PHASE_COLUMNS[home_phase]
    data = stations.copy()
    data["istasyon_kullanilabilir_guc"] = data[power_column].where(data[support_column], 0.0)
    reasons = []
    for _, row in data.iterrows():
        reason = []
        if row["fiyat"] > budget:
            reason.append("Bütçeyi aşıyor")
        if not row[support_column]:
            reason.append("Ev fazını desteklemiyor")
        reasons.append(reason)
    data["elenme_nedenleri"] = reasons
    suitable = data.loc[data["elenme_nedenleri"].map(len).eq(0)].copy()
    excluded = data.loc[data["elenme_nedenleri"].map(len).gt(0)].copy()
    return suitable.reset_index(drop=True), excluded.reset_index(drop=True)


def add_derived_values(suitable, daily_km, vehicle_ac_kw, battery_kwh,
                       consumption, home_max_kw):
    """İdeal süreyi kayıpsız sabit güç varsayımıyla hesapla."""
    values = [daily_km, vehicle_ac_kw, battery_kwh, consumption, home_max_kw]
    if not np.isfinite(values).all() or daily_km < 0 or any(v <= 0 for v in values[1:]):
        raise ValueError("Günlük km negatif olamaz; diğer girdiler pozitif ve sonlu olmalıdır.")
    result = suitable.copy()
    result["efektif_guc"] = np.minimum(
        result["istasyon_kullanilabilir_guc"], min(vehicle_ac_kw, home_max_kw)
    )
    result["gunluk_enerji"] = daily_km * consumption / 100
    result["sarj_suresi"] = result["gunluk_enerji"] / result["efektif_guc"]
    result["tam_sarj_suresi"] = battery_kwh / result["efektif_guc"]
    return result
