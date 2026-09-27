"""Teknik filtre → AHP → TOPSIS → ELECTRE I karar akışı.

run_decision tek, JSON'a dönüştürülebilir bir denetim sonucu üretir.
"""

from pathlib import Path

import numpy as np

from algorithms.ahp import calculate_ahp
from algorithms.electre import calculate_electre
from algorithms.filter import add_derived_values, filter_stations
from algorithms.topsis import calculate_topsis
from utils.decision_config import load_ahp_matrix, load_decision_config
from utils.helpers import load_stations


ROOT = Path(__file__).resolve().parent
DEFAULT_STATIONS = ROOT / "data" / "sarj_istasyonlari.csv"
DEFAULT_CONFIG = ROOT / "config" / "decision_config.json"


class InconsistentAHPError(ValueError):
    """AHP karşılaştırmaları ana karar akışı için fazla tutarsız."""

    def __init__(self, cr):
        self.cr = cr
        super().__init__(f"AHP matrisi tutarsız: CR={cr:.4f} ≥ 0.10")


def detect_method_disagreement(ranking, outranking):
    """TOPSIS birincisine karşı tek yönlü ELECTRE üstünlüğü var mı?"""
    if len(ranking) == 0:
        return []
    winner = int(ranking[0])
    return [j for j in range(len(outranking))
            if j != winner and outranking[j, winner] and not outranking[winner, j]]


def _native(value):
    """NumPy ve pandas sonuçlarını JSON'a uygun Python tiplerine dönüştür."""
    if isinstance(value, np.ndarray):
        return _native(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_native(item) for item in value]
    return value


def run_decision(user_inputs, stations_path=DEFAULT_STATIONS,
                 config_path=DEFAULT_CONFIG, matrix_path=None, assumptions=None):
    """Bir karar için tüm aşamaları sırayla çalıştır ve audit sözlüğü döndür.

    Bilinmeyen ev fazı çözümlenmiş bir teknik girdi değildir; bu fonksiyon
    yalnızca monofaz veya trifaz ile nihai sıralama oluşturur.
    """
    required = {"daily_km", "vehicle_ac_kw", "battery_kwh", "consumption",
                "home_phase", "home_max_kw", "budget"}
    missing = required - set(user_inputs)
    if missing:
        raise ValueError(f"Kullanıcı girdileri eksik: {', '.join(sorted(missing))}")

    # 1. CSV doğrulama; 2. teknik filtre; 3. kullanıcıya özgü türetilmiş değerler.
    stations = load_stations(stations_path)
    suitable, excluded = filter_stations(stations, user_inputs["home_phase"],
                                          user_inputs["budget"])
    suitable = add_derived_values(
        suitable, user_inputs["daily_km"], user_inputs["vehicle_ac_kw"],
        user_inputs["battery_kwh"], user_inputs["consumption"],
        user_inputs["home_max_kw"])
    result = {
        "status": "ok" if not suitable.empty else "no_alternatives",
        "user_inputs": dict(user_inputs),
        "input_assumptions": list(assumptions or []),
        "filtered_alternatives": suitable.drop(columns="elenme_nedenleri").to_dict("records"),
        "exclusions": [
            {"id": row["id"], "marka": row["marka"], "model": row["model"],
             "reasons": row["elenme_nedenleri"]}
            for _, row in excluded.iterrows()
        ],
        "ahp_matrix": None, "ahp_weights": None,
        "lambda_max": None, "CI": None, "CR": None,
        "topsis": None, "electre": None, "final_ranking": [],
        "method_disagreement": False, "disagreeing_alternatives": [],
        "explanation": [],
    }
    if suitable.empty:
        result["explanation"] = ["Girilen bütçe ve faz için uygun cihaz bulunamadı."]
        return _native(result)

    # 4. AHP: matrisi harici dosyadan al ve CR kapısını uygula.
    config = load_decision_config(config_path)
    criteria = config["criteria"]
    names = [item["name"] for item in criteria]
    matrix, description = load_ahp_matrix(matrix_path or config["matrix_path"], names)
    ahp = calculate_ahp(matrix)
    if not ahp["consistent"]:
        raise InconsistentAHPError(ahp["cr"])
    result.update({"ahp_matrix": matrix, "ahp_matrix_description": description,
                   "ahp_weights": dict(zip(names, ahp["weights"])),
                   "lambda_max": ahp["lambda_max"], "CI": ahp["ci"], "CR": ahp["cr"],
                   "criteria": criteria})

    raw = suitable[names].to_numpy(dtype=float)
    directions = [item["type"] for item in criteria]
    ids = suitable["id"].tolist()

    # 5. TOPSIS nihai sıralamayı belirler.
    topsis = calculate_topsis(raw, ahp["weights"], directions)
    result["topsis"] = {
        "raw_matrix": topsis["raw_matrix"],
        "normalized_matrix": topsis["normalized"],
        "weighted_normalized_matrix": topsis["weighted"],
        "positive_ideal": topsis["ideal_positive"],
        "negative_ideal": topsis["ideal_negative"],
        "S_plus": topsis["s_positive"], "S_minus": topsis["s_negative"],
        "C_star": topsis["scores"],
        "rank": [ids[int(i)] for i in topsis["ranking"]],
    }
    result["final_ranking"] = [
        {"rank": rank, "id": ids[int(i)], "marka": suitable.iloc[int(i)]["marka"],
         "model": suitable.iloc[int(i)]["model"], "C_star": topsis["scores"][int(i)]}
        for rank, i in enumerate(topsis["ranking"], 1)
    ]

    # 6. ELECTRE yalnızca yönlü üstünlük bilgisidir.
    threshold_config = config["electre_thresholds"]
    kwargs = ({"concordance_threshold": threshold_config["concordance"],
               "discordance_threshold": threshold_config["discordance"]}
              if threshold_config["mode"] == "fixed" else {})
    electre = calculate_electre(raw, ahp["weights"], directions, **kwargs)
    result["electre"] = {
        "normalized_matrix": electre["normalized"],
        "weighted_normalized_matrix": electre["weighted"],
        "concordance_sets": [
            {"from": ids[i], "to": ids[j], "criteria": [names[k] for k in indices]}
            for (i, j), indices in electre["concordance_sets"].items()
        ],
        "discordance_sets": [
            {"from": ids[i], "to": ids[j], "criteria": [names[k] for k in indices]}
            for (i, j), indices in electre["discordance_sets"].items()
        ],
        "concordance_matrix": electre["concordance"],
        "discordance_matrix": electre["discordance"],
        "concordance_threshold": electre["concordance_threshold"],
        "discordance_threshold": electre["discordance_threshold"],
        "threshold_mode": threshold_config["mode"],
        "outranking_matrix": electre["outranking"],
    }

    # 7. Yöntem farkı; üstünlük yokluğu anlaşmazlık değildir.
    disagreeing = detect_method_disagreement(topsis["ranking"], electre["outranking"])
    result["method_disagreement"] = bool(disagreeing)
    result["disagreeing_alternatives"] = [ids[i] for i in disagreeing]

    # 8. Açıklama; günlük süre teorik ve kayıpsızdır.
    winner = suitable.iloc[int(topsis["ranking"][0])]
    result["explanation"] = [
        "Cihaz girilen bütçeye ve ev fazına uygundur.",
        "AHP ağırlıklarıyla hesaplanan TOPSIS yakınlık katsayısında ilk sıradadır.",
        f"Günlük enerji ihtiyacı {winner['gunluk_enerji']:.2f} kWh; "
        f"ideal teorik şarj süresi yaklaşık {winner['sarj_suresi']:.2f} saattir. "
        "Şarj kayıpları dahil değildir.",
    ]
    if disagreeing:
        result["explanation"].append(
            "Yöntemler arasında farklılık bulunmaktadır: "
            f"{', '.join(ids[i] for i in disagreeing)} ELECTRE I'de TOPSIS birincisine "
            "tek yönlü üstünlük sağlamaktadır. Nihai sıralama TOPSIS'e göredir."
        )
    return _native(result)
