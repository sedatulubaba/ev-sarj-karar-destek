"""Bütçe ve faz filtresi ile günlük enerji ve süre hesapları."""

import numpy as np


def filter_stations(stations, daily_km, vehicle_ac_kw, battery_kwh,
                    consumption, home_phase, home_max_kw, budget):
    """Uygun istasyonları ve elenenlerin nedenlerini döndürür.

    Faz dönüşümü veya farklı fazda düşük güçte çalışma varsayılmaz.
    Süreler sabit güç varsayımıyla hesaplanır; şarj kayıpları dahil değildir.
    """
    values = [daily_km, vehicle_ac_kw, battery_kwh, consumption, home_max_kw, budget]
    if not np.isfinite(values).all():
        raise ValueError("Girdiler sonlu sayılar olmalıdır.")
    if daily_km < 0 or any(value <= 0 for value in values[1:]):
        raise ValueError("Günlük km negatif olamaz; diğer sayısal girdiler pozitif olmalıdır.")
    if home_phase not in ["monofaz", "trifaz"]:
        raise ValueError("Geçersiz ev fazı.")
    data = stations.copy()
    reasons = []
    for _, row in data.iterrows():
        reason = []
        if row["fiyat"] > budget:
            reason.append("Bütçeyi aşıyor")
        if row["faz"] != home_phase:
            reason.append("Faz uyumsuz")
        reasons.append("; ".join(reason))
    data["elenme_nedeni"] = reasons
    suitable = data.loc[data["elenme_nedeni"].eq("")].copy()
    excluded = data.loc[data["elenme_nedeni"].ne("")].copy()
    suitable["efektif_guc"] = np.minimum(
        suitable["guc_kw"], min(vehicle_ac_kw, home_max_kw)
    )
    suitable["gunluk_enerji"] = daily_km * consumption / 100
    suitable["sarj_suresi"] = suitable["gunluk_enerji"] / suitable["efektif_guc"]
    suitable["tam_sarj_suresi"] = battery_kwh / suitable["efektif_guc"]
    return suitable.reset_index(drop=True), excluded.reset_index(drop=True)
