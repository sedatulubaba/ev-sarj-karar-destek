"""Çalıştırma: python -m streamlit run app.py"""

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from algorithms.ahp import calculate_ahp
from algorithms.electre import calculate_electre
from algorithms.filter import filter_stations
from algorithms.topsis import calculate_topsis
from utils.helpers import CRITERIA, load_stations


def get_user_inputs():
    """Araç, ev ve bütçe bilgilerini kenar çubuğundan alır."""
    with st.sidebar:
        st.header("Araç ve ev bilgileri")
        return {
            "daily_km": st.number_input("Günlük ortalama km", min_value=0.0, value=50.0),
            "vehicle_ac_kw": st.number_input("Aracın maksimum AC gücü (kW)", min_value=0.1, value=11.0),
            "battery_kwh": st.number_input("Batarya kapasitesi (kWh)", min_value=0.1, value=60.0),
            "consumption": st.number_input("Araç tüketimi (kWh/100 km)", min_value=0.1, value=18.0),
            "home_phase": st.selectbox("Ev elektrik altyapısı", ["monofaz", "trifaz"]),
            "home_max_kw": st.number_input("Şarja ayrılabilecek ev gücü (kW)", min_value=0.1, value=7.4),
            "budget": st.number_input("Maksimum cihaz bütçesi (TL)", min_value=1.0, value=30000.0, step=1000.0),
        }


def get_ahp_matrix(labels):
    """Üst üçgeni kullanıcıdan alır; ters değerleri otomatik tamamlar."""
    matrix = np.ones((len(labels), len(labels)))
    scale = [1 / 9, 1 / 8, 1 / 7, 1 / 6, 1 / 5, 1 / 4, 1 / 3, 1 / 2,
             1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]

    def format_scale(value):
        return f"1/{round(1 / value)}" if value < 1 else str(int(value))

    with st.expander("AHP ikili karşılaştırmalarını düzenle"):
        st.write("1: eşit önem; 3: orta; 5: güçlü; 7: çok güçlü; 9: aşırı önem. "
                 "1'den büyük değer soldaki kriteri, kesirli değer sağdaki kriteri önemser.")
        st.caption("Başlangıçta tüm kriterler eşit önemdedir. Fiyatın önemli olması düşük fiyatı tercih ettirir.")
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                value = st.selectbox(f"{labels[i]} / {labels[j]}", scale, index=8,
                                      format_func=format_scale, key=f"ahp_{i}_{j}")
                matrix[i, j] = value
                matrix[j, i] = 1 / value
        st.dataframe(pd.DataFrame(matrix, index=labels, columns=labels))
    return matrix


def show_results(suitable, topsis, electre, weights, labels):
    """Öneriyi, gerekçelerini ve tüm alternatiflerin sıralamasını gösterir."""
    best_index = int(topsis["ranking"][0])
    best = suitable.iloc[best_index]
    st.header("Önerilen şarj istasyonu")
    st.subheader(f"{best['marka']} — {best['model']}")
    columns = st.columns(4)
    columns[0].metric("TOPSIS skoru", f"{topsis['scores'][best_index]:.4f}")
    columns[1].metric("Efektif güç", f"{best['efektif_guc']:.2f} kW")
    columns[2].metric("Günlük şarj süresi", f"{best['sarj_suresi']:.2f} saat")
    columns[3].metric("Cihaz fiyatı", f"{best['fiyat']:,.0f} TL")
    st.write(f"ELECTRE: {int(electre['outgoing'][best_index])} alternatife üstünlük ilişkisi kuruyor; "
             f"{int(electre['incoming'][best_index])} alternatif bu cihaza üstünlük ilişkisi kuruyor.")
    st.markdown("- Bütçe ve faz uygunluğu koşullarını sağlıyor.\n"
                "- Seçilen AHP ağırlıklarıyla en yüksek TOPSIS yakınlık katsayısına sahip.\n"
                f"- Günlük {best['gunluk_enerji']:.2f} kWh ihtiyacı yaklaşık "
                f"{best['sarj_suresi']:.2f} saatte karşılıyor.")
    important = np.argsort(-weights, kind="stable")[:2]
    for index in important:
        key = list(CRITERIA)[index]
        st.write(f"• Öncelikli kriter: {labels[index]} (ağırlık %{weights[index] * 100:.1f}); "
                 f"bu cihazın değeri {best[key]:.2f}.")
    if np.isclose(topsis["scores"], topsis["scores"][best_index], atol=1e-12, rtol=0).sum() > 1:
        st.info("En yüksek skorda eşitlik var. Öneri, CSV sırasındaki ilk eşit alternatif olarak gösterildi.")
    if len(suitable) == 1:
        st.info("Tek uygun alternatif var; göreli karşılaştırma yapılamadığından TOPSIS skoru 0.5 kabul edildi.")
    st.caption(f"İdeal koşullarda 0–100% şarj süresi: {best['tam_sarj_suresi']:.2f} saat. "
               "TOPSIS skoru bir başarı olasılığı değildir; mevcut alternatiflere göre hesaplanır.")

    results = suitable.copy()
    results["TOPSIS skoru"] = topsis["scores"]
    results["ELECTRE üstünlük sayısı"] = electre["outgoing"]
    results["ELECTRE gelen üstünlük"] = electre["incoming"]
    results = results.iloc[topsis["ranking"]].drop(columns="elenme_nedeni")
    results.insert(0, "Sıra", range(1, len(results) + 1))
    st.subheader("Tüm uygun alternatifler")
    st.dataframe(results, hide_index=True)
    st.download_button("Sonuçları CSV indir", results.to_csv(index=False).encode("utf-8-sig"),
                       file_name="sarj_sonuclari.csv", mime="text/csv")


def main():
    st.set_page_config(page_title="Ev Tipi Şarj Karar Desteği", page_icon="⚡", layout="wide")
    st.title("⚡ Ev Tipi Şarj İstasyonu Karar Destek Sistemi")
    st.write("Teknik filtreleme → AHP → ELECTRE I → TOPSIS")
    st.caption("Akademik örnek: CSV'deki ürünler ve fiyatlar temsili verilerdir. "
               "Bütçe yalnızca cihaz fiyatını kapsar.")
    inputs = get_user_inputs()
    try:
        stations = load_stations(Path(__file__).parent / "data" / "sarj_istasyonlari.csv")
        suitable, excluded = filter_stations(stations, **inputs)
    except (ValueError, OSError) as error:
        st.error(f"Veriler okunamadı veya doğrulanamadı: {error}")
        st.stop()

    st.header("1. Teknik filtreleme")
    energy = inputs["daily_km"] * inputs["consumption"] / 100
    st.write(f"Günlük enerji ihtiyacı: **{energy:.2f} kWh** · "
             f"Uygun cihaz: **{len(suitable)} / {len(stations)}**")
    st.caption("Faz uyumu aynı faz şartıyla değerlendirilir. Efektif güç = min(araç, ev, istasyon). "
               "Süre = günlük enerji / efektif güç. Kayıplar ve güç değişimleri süreye dahil değildir; "
               "verimlilik yalnızca karar kriteridir.")
    if energy > inputs["battery_kwh"]:
        st.warning("Günlük enerji ihtiyacı batarya kapasitesini aşıyor; gün içinde ek şarj gerekebilir.")
    with st.expander("CSV verileri ve elenme nedenleri"):
        st.dataframe(stations, hide_index=True)
        st.dataframe(excluded[["id", "marka", "model", "elenme_nedeni"]], hide_index=True)
    if suitable.empty:
        st.warning("Uygun istasyon bulunamadı. Bütçeyi ve CSV'deki faz seçeneklerini kontrol edin.")
        st.stop()

    st.header("2. AHP kriter ağırlıkları")
    labels = [value[0] for value in CRITERIA.values()]
    directions = [value[1] for value in CRITERIA.values()]
    ahp = calculate_ahp(get_ahp_matrix(labels))
    st.dataframe(pd.DataFrame({"Kriter": labels, "Ağırlık": ahp["weights"]}), hide_index=True)
    st.write(f"λ_max ≈ {ahp['lambda_max']:.4f} · CI = {ahp['ci']:.4f} · CR = {ahp['cr']:.4f}")
    if not ahp["consistent"]:
        st.error("CR ≥ 0.10: karşılaştırmalar tutarsız. Sıralama için ikili karşılaştırmaları düzenleyin.")
        st.stop()
    st.success("CR < 0.10: karşılaştırmalar tutarlı.")

    st.header("3. ELECTRE I üstünlük analizi")
    left, right = st.columns(2)
    c_threshold = left.slider("Concordance (uyum) alt eşiği", 0.0, 1.0, 0.65, 0.05)
    d_threshold = right.slider("Discordance (uyumsuzluk) üst eşiği", 0.0, 1.0, 0.35, 0.05)
    matrix = suitable[list(CRITERIA)].to_numpy(dtype=float)
    electre = calculate_electre(matrix, ahp["weights"], directions, c_threshold, d_threshold)
    ids = suitable["id"].tolist()
    st.caption("Satırdaki cihazın sütundakine üstünlüğü: uyum ≥ alt eşik ve uyumsuzluk ≤ üst eşik. "
               "ELECTRE döngü veya karşılaştırılamayan çiftler üretebilir; TOPSIS'e ek bilgi sunar, "
               "alternatifleri ayrıca elemez. Köşegen değerlendirilmez.")
    with st.expander("ELECTRE matrisleri ve kriter kümeleri"):
        for key, title in [("concordance", "Uyum matrisi"), ("discordance", "Uyumsuzluk matrisi"),
                           ("outranking", "Üstünlük matrisi (1 = ilişki var)")]:
            st.write(title)
            values = electre[key].astype(int) if key == "outranking" else electre[key]
            st.dataframe(pd.DataFrame(values, index=ids, columns=ids))
        sets = []
        for (i, j), indices in electre["concordance_sets"].items():
            sets.append({"Çift": f"{ids[i]} → {ids[j]}",
                         "Uyum kümesi": ", ".join(labels[k] for k in indices) or "∅",
                         "Uyumsuzluk kümesi": ", ".join(labels[k] for k in electre["discordance_sets"][(i, j)]) or "∅"})
        st.dataframe(pd.DataFrame(sets), hide_index=True)

    st.header("4. TOPSIS sıralaması")
    topsis = calculate_topsis(matrix, ahp["weights"], directions)
    with st.expander("Hesaplama ayrıntıları"):
        st.write("Fiyat maliyet; diğer kriterler faydadır. C = S− / (S+ + S−).")
        for title, values in [("Karar matrisi", matrix), ("Normalize matris", topsis["normalized"]),
                              ("Ağırlıklı matris", topsis["weighted"])]:
            st.write(title)
            st.dataframe(pd.DataFrame(values, index=ids, columns=labels))
        st.write("İdeal çözümler")
        st.dataframe(pd.DataFrame([topsis["ideal_positive"], topsis["ideal_negative"]],
                                 index=["Pozitif ideal", "Negatif ideal"], columns=labels))
        st.dataframe(pd.DataFrame({"S+": topsis["s_positive"], "S−": topsis["s_negative"],
                                   "C": topsis["scores"]}, index=ids))
        st.write("AHP sütun normalizasyonu")
        st.dataframe(pd.DataFrame(ahp["normalized"], index=labels, columns=labels))
    show_results(suitable, topsis, electre, ahp["weights"], labels)


if __name__ == "__main__":
    main()
