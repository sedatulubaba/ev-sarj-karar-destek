"""Ev tipi şarj cihazı seçim arayüzü. Çalıştırma: streamlit run app.py"""

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from algorithms.ahp import calculate_ahp
from algorithms.electre import calculate_electre
from algorithms.filter import filter_stations
from algorithms.topsis import calculate_topsis
from utils.helpers import CRITERIA, load_stations


# Bilinmeyen değerler yalnızca ön değerlendirme için kullanılır.
ASSUMED = {"vehicle_ac_kw": 7.4, "battery_kwh": 60.0,
           "consumption": 18.0, "home_max_kw": 3.7}


def apply_style():
    """Boşluk, sakin renkler ve küçük ekranlarda rahat okuma."""
    st.markdown("""
    <style>
      .block-container { max-width: 760px; padding-top: 3.5rem; padding-bottom: 4rem; }
      h1, h2, h3 { letter-spacing: -0.03em; color: #1d1d1f !important; }
      h1 { font-size: clamp(2rem, 5vw, 2.75rem) !important; font-weight: 650 !important;
           line-height: 1.16 !important; margin-bottom: .6rem !important; }
      h2 { font-size: 1.4rem !important; font-weight: 620 !important; margin-top: 2rem !important; }
      h3 { font-size: 1.15rem !important; font-weight: 620 !important; margin-top: 1.8rem !important; }
      .field-label { color: #1d1d1f !important; font-size: 1rem !important;
           font-weight: 550 !important; margin: 0 0 .35rem !important; }
      [data-testid="stWidgetLabel"] p { color: #303034 !important; font-size: .9rem !important; }
      [data-testid="stCheckbox"] { margin-top: -.25rem; margin-bottom: 1rem; }
      [data-testid="stForm"] { border: 0; padding: 0; background: transparent; }
      [data-testid="stFormSubmitButton"] button { background: #1d1d1f; color: #fff;
          border: 1px solid #1d1d1f; border-radius: 10px; min-height: 2.9rem;
          padding: .45rem 1.3rem; box-shadow: none; }
      [data-testid="stFormSubmitButton"] button:hover { background: #3a3a3c; color: #fff;
          border-color: #3a3a3c; }
      [data-testid="stExpander"] { border: 1px solid #e5e5e7; border-radius: 10px;
          background: #fff; box-shadow: none; }
      hr { border-color: #e5e5e7 !important; }
      @media (max-width: 640px) {
        .block-container { padding: 1.7rem 1.1rem 3rem; }
        h1 { font-size: 2rem !important; }
      }
    </style>""", unsafe_allow_html=True)


def optional_number(label, key, default, minimum, step):
    """Her teknik sayısal alan için ayrı Bilmiyorum seçimi."""
    st.markdown(f'<p class="field-label">{label}</p>', unsafe_allow_html=True)
    unknown = st.session_state.get(f"{key}_unknown", False)
    value = st.number_input(label, min_value=minimum, value=default, step=step,
                            disabled=unknown, key=key, label_visibility="collapsed")
    unknown = st.checkbox("Bilmiyorum", key=f"{key}_unknown")
    return (ASSUMED[key] if unknown else value), unknown


def get_user_inputs():
    """Üç bölümlü formdan değerleri ve varsayım açıklamalarını alır."""
    assumptions = []
    with st.form("charging_form"):
        st.subheader("Araç")
        vehicle_ac_kw, unknown = optional_number("Maksimum AC şarj gücü (kW)",
                                                  "vehicle_ac_kw", 11.0, 0.1, 0.1)
        if unknown:
            assumptions.append("Araç AC gücü 7,4 kW varsayıldı.")
        battery_kwh, unknown = optional_number("Batarya kapasitesi (kWh)",
                                                "battery_kwh", 60.0, 0.1, 0.1)
        if unknown:
            assumptions.append("Batarya kapasitesi 60 kWh varsayıldı.")
        consumption, unknown = optional_number("Araç tüketimi (kWh/100 km)",
                                                "consumption", 18.0, 0.1, 0.1)
        if unknown:
            assumptions.append("Tüketim 18 kWh/100 km varsayıldı.")
        st.divider()
        st.subheader("Ev")
        st.markdown('<p class="field-label">Elektrik altyapısı</p>', unsafe_allow_html=True)
        phase_choice = st.selectbox("Elektrik altyapısı", ["Monofaz", "Trifaz", "Bilmiyorum"],
                                    key="home_phase", label_visibility="collapsed")
        home_max_kw, unknown = optional_number("Şarja ayrılabilecek maksimum güç (kW)",
                                               "home_max_kw", 7.4, 0.1, 0.1)
        if unknown:
            assumptions.append("Evde şarja ayrılabilecek güç 3,7 kW varsayıldı.")
        if phase_choice == "Bilmiyorum":
            assumptions.append("Ev fazı bilinmiyor; iki faz seçeneği ayrı ayrı değerlendirildi.")
        st.divider()
        st.subheader("Kullanım")
        st.markdown('<p class="field-label">Günlük ortalama km</p>', unsafe_allow_html=True)
        daily_km = st.number_input("Günlük ortalama km", min_value=0.0, value=50.0,
                                   step=1.0, key="daily_km", label_visibility="collapsed")
        st.markdown('<p class="field-label">Maksimum cihaz bütçesi (TL)</p>', unsafe_allow_html=True)
        budget = st.number_input("Maksimum cihaz bütçesi (TL)", min_value=1.0,
                                 value=30000.0, step=1000.0, key="budget",
                                 label_visibility="collapsed")
        submitted = st.form_submit_button("Uygun şarj cihazlarını göster", type="primary")
    inputs = {"daily_km": daily_km, "vehicle_ac_kw": vehicle_ac_kw,
              "battery_kwh": battery_kwh, "consumption": consumption,
              "home_max_kw": home_max_kw, "budget": budget}
    return submitted, inputs, phase_choice, assumptions


def get_suitable_stations(stations, inputs, phase_choice):
    """Bilinmeyen fazda mevcut filtreyi iki faz için ayrı çalıştırır."""
    phases = (["monofaz", "trifaz"] if phase_choice == "Bilmiyorum"
              else [phase_choice.lower()])
    parts = []
    for phase in phases:
        suitable, _ = filter_stations(stations, home_phase=phase, **inputs)
        parts.append(suitable)
    return pd.concat(parts, ignore_index=True)


def analyze(suitable):
    """Mevcut AHP, ELECTRE I ve TOPSIS fonksiyonlarını kullanır."""
    labels = [item[0] for item in CRITERIA.values()]
    directions = [item[1] for item in CRITERIA.values()]
    # Ana ekranda karşılaştırma formu yok; eşit ağırlıklar seçilmiştir.
    ahp = calculate_ahp(np.ones((len(CRITERIA), len(CRITERIA))))
    matrix = suitable[list(CRITERIA)].to_numpy(dtype=float)
    electre = calculate_electre(matrix, ahp["weights"], directions)
    topsis = calculate_topsis(matrix, ahp["weights"], directions)
    return ahp, electre, topsis, labels


def show_result(suitable, topsis, inputs, phase_choice, assumptions):
    """Öneri ve en fazla üç alternatif için sade karşılaştırma."""
    best = suitable.iloc[int(topsis["ranking"][0])]
    st.divider()
    st.header("Size önerilen cihaz")
    st.subheader(f"{best['marka']} {best['model']}")
    st.write(f"**Fiyat:** {best['fiyat']:,.0f} TL")
    st.write(f"**Efektif şarj gücü:** {best['efektif_guc']:.1f} kW")
    st.write(f"**Tahmini günlük şarj süresi:** {best['sarj_suresi']:.1f} saat")
    if assumptions:
        st.write("**Teknik uygunluk:** Ön değerlendirme. Bilinmeyen bilgileri doğrulayın.")
        st.caption(" ".join(assumptions))
    else:
        st.write("**Teknik uygunluk:** Girilen bütçe, faz ve güç sınırlarına uygun.")
    st.write("**Neden önerildi?**")
    st.markdown("- Bütçe ve girilen teknik koşullar içinde değerlendirildi.\n"
                "- Fiyat, kullanılabilir güç, güvenlik, akıllı özellik, garanti ve "
                "verimlilik birlikte karşılaştırıldığında ilk sırada yer aldı.")
    if phase_choice == "Bilmiyorum":
        st.caption(f"Bu cihaz {best['faz']} bağlantı gerektirir. Satın almadan önce evinizin fazını doğrulayın.")
    if inputs["daily_km"] * inputs["consumption"] / 100 > inputs["battery_kwh"]:
        st.info("Tahmini günlük enerji ihtiyacı batarya kapasitesinden fazla; gün içinde ek şarj gerekebilir.")
    st.caption("Süre sabit güç varsayımıyla hesaplanır; şarj kayıpları ve kurulum bedeli dahil değildir. "
               "Ürünler ve fiyatlar temsili veridir.")
    if len(suitable) > 1:
        st.subheader("Diğer uygun seçeneklerle karşılaştırın")
        top = suitable.iloc[topsis["ranking"][:3]]
        comparison = pd.DataFrame({
            "Cihaz": top["marka"].to_numpy() + " " + top["model"].to_numpy(),
            "Fiyat (TL)": top["fiyat"].to_numpy(),
            "Efektif güç (kW)": top["efektif_guc"].round(1).to_numpy(),
            "Günlük süre (saat)": top["sarj_suresi"].round(1).to_numpy(),
            "Faz": top["faz"].to_numpy(),
        })
        st.dataframe(comparison, hide_index=True, width="stretch")


def show_method():
    with st.expander("Değerlendirme yöntemi"):
        st.write("**Teknik uygunluk:** Cihaz fiyatı bütçeye, fazı ev altyapısına göre kontrol edilir. "
                 "Şarj gücü araç, ev ve cihaz sınırlarının en küçüğüdür.")
        st.write("**AHP:** Ölçütlere ağırlık verir. Bu sade arayüzde ölçütler eşit önemle değerlendirilir.")
        st.write("**ELECTRE I:** Cihazların birbirine göre üstünlük ilişkisini inceler.")
        st.write("**TOPSIS:** Uygun cihazları ideal seçeneğe yakınlıklarına göre sıralar.")


def show_calculation_details(suitable=None, ahp=None, electre=None, topsis=None, labels=None):
    with st.expander("Hesaplama detaylarını göster"):
        if suitable is None:
            st.write("Sonuçları görmek için formu doldurup butona basın.")
            return
        st.write("**AHP kriter ağırlıkları**")
        st.dataframe(pd.DataFrame({"Kriter": labels, "Ağırlık": ahp["weights"]}),
                     hide_index=True, width="stretch")
        st.write(f"**CR:** {ahp['cr']:.4f} (0,10 altında: tutarlı)")
        st.write("**ELECTRE I üstünlük sonuçları**")
        ids = suitable["id"].tolist()
        st.dataframe(pd.DataFrame({"Cihaz": ids,
                                   "Üstün olduğu cihaz sayısı": electre["outgoing"],
                                   "Üstün gelen cihaz sayısı": electre["incoming"]}),
                     hide_index=True, width="stretch")
        st.caption("Satırdaki cihaz sütundaki cihaza üstünse değer 1'dir.")
        st.dataframe(pd.DataFrame(electre["outranking"].astype(int), index=ids, columns=ids),
                     width="stretch")
        st.write("**TOPSIS skorları**")
        scores = pd.DataFrame({"Cihaz": ids, "Skor": topsis["scores"]})
        st.dataframe(scores.iloc[topsis["ranking"]], hide_index=True, width="stretch")
        st.caption("AHP karşılaştırmaları eşit önemlidir. ELECTRE eşikleri: uyum 0,65; "
                   "uyumsuzluk 0,35. TOPSIS skoru seçenekler arası göreli sıralamadır.")


def main():
    st.set_page_config(page_title="Ev şarj cihazı seçimi", layout="centered",
                       initial_sidebar_state="collapsed")
    apply_style()
    st.title("Aracınız için uygun ev şarj cihazını bulun")
    st.write("Aracınız, eviniz ve günlük kullanımınıza göre uygun seçenekleri karşılaştıralım.")
    submitted, inputs, phase_choice, assumptions = get_user_inputs()
    if not submitted:
        show_method()
        show_calculation_details()
        return
    try:
        stations = load_stations(Path(__file__).parent / "data" / "sarj_istasyonlari.csv")
        suitable = get_suitable_stations(stations, inputs, phase_choice)
        if suitable.empty:
            st.warning("Bu bilgilerle uygun cihaz bulunamadı. Bütçenizi veya ev bilgilerinizi kontrol edin.")
            show_method()
            show_calculation_details()
            return
        ahp, electre, topsis, labels = analyze(suitable)
    except (ValueError, OSError) as error:
        st.error(f"Hesaplama tamamlanamadı: {error}")
        return
    show_result(suitable, topsis, inputs, phase_choice, assumptions)
    show_method()
    show_calculation_details(suitable, ahp, electre, topsis, labels)


if __name__ == "__main__":
    main()
