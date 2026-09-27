"""Sade kullanıcı arayüzü; karar hesabı decision_engine modülündedir."""

import json

import pandas as pd
import streamlit as st

from decision_engine import run_decision


# Bilinmeyen sayısal değerler yalnızca ön değerlendirme için kullanılır.
ASSUMED = {"vehicle_ac_kw": 7.4, "battery_kwh": 60.0,
           "consumption": 18.0, "home_max_kw": 3.7}


def apply_style():
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
    st.markdown(f'<p class="field-label">{label}</p>', unsafe_allow_html=True)
    unknown = st.session_state.get(f"{key}_unknown", False)
    value = st.number_input(label, min_value=minimum, value=default, step=step,
                            disabled=unknown, key=key, label_visibility="collapsed")
    unknown = st.checkbox("Bilmiyorum", key=f"{key}_unknown")
    return (ASSUMED[key] if unknown else value), unknown


def get_user_inputs():
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
              "home_phase": phase_choice.lower(), "home_max_kw": home_max_kw,
              "budget": budget}
    return submitted, inputs, assumptions


def show_result(result):
    suitable = pd.DataFrame(result["filtered_alternatives"])
    ranked = result["final_ranking"]
    best = suitable.set_index("id").loc[ranked[0]["id"]]
    st.divider()
    st.header("Size önerilen cihaz")
    st.subheader(f"{best['marka']} {best['model']}")
    st.write(f"**Fiyat:** {best['fiyat']:,.0f} TL")
    st.write(f"**Efektif şarj gücü:** {best['efektif_guc']:.1f} kW")
    st.write(f"**Tahmini günlük şarj süresi:** {best['sarj_suresi']:.1f} saat")
    if result["input_assumptions"]:
        st.write("**Teknik uygunluk:** Ön değerlendirme. Bilinmeyen bilgileri doğrulayın.")
        st.caption(" ".join(result["input_assumptions"]))
    else:
        st.write("**Teknik uygunluk:** Girilen bütçe, faz ve güç sınırlarına uygun.")
    st.write("**Neden önerildi?**")
    for explanation in result["explanation"]:
        if explanation.startswith("Yöntemler arasında"):
            st.warning(explanation)
        else:
            st.markdown(f"- {explanation}")
    if result["user_inputs"]["daily_km"] * result["user_inputs"]["consumption"] / 100 > result["user_inputs"]["battery_kwh"]:
        st.info("Tahmini günlük enerji ihtiyacı batarya kapasitesinden fazla; gün içinde ek şarj gerekebilir.")
    st.caption("Süre ideal ve teoriktir; şarj kayıpları ve kurulum bedeli dahil değildir. "
               "Ürünler ve fiyatlar temsili veridir.")
    if len(ranked) > 1:
        st.subheader("Diğer uygun seçeneklerle karşılaştırın")
        by_id = suitable.set_index("id")
        rows = []
        for item in ranked[:3]:
            row = by_id.loc[item["id"]]
            rows.append({"Cihaz": f"{row['marka']} {row['model']}", "Fiyat (TL)": row["fiyat"],
                         "Efektif güç (kW)": round(row["efektif_guc"], 1),
                         "Günlük ideal süre (saat)": round(row["sarj_suresi"], 1)})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def show_method():
    with st.expander("Değerlendirme yöntemi"):
        st.write("**Teknik uygunluk:** Bütçe ve ev fazı kontrol edilir; cihazın o fazda "
                 "sunabildiği güç araç ve ev sınırlarıyla karşılaştırılır.")
        st.write("**AHP:** Kriter ağırlıkları harici karşılaştırma matrisinden hesaplanır. "
                 "Mevcut dosya örnek amaçlıdır; CR 0,10 veya üzerindeyse karar verilmez.")
        st.write("**TOPSIS:** Nihai sıralamayı belirler.")
        st.write("**ELECTRE I:** Üstünlük ilişkilerini ayrıca inceler; sıralamayı değiştirmez.")


def show_calculation_details(result=None):
    with st.expander("Hesaplama detaylarını göster"):
        if result is None:
            st.write("Hesaplama sonuçları için formu doldurup butona basın.")
            return
        st.write("**AHP kriter ağırlıkları**")
        st.caption(result["ahp_matrix_description"])
        st.dataframe(pd.DataFrame(result["ahp_weights"].items(), columns=["Kriter", "Ağırlık"]),
                     hide_index=True, width="stretch")
        st.write(f"**λ_max:** {result['lambda_max']:.4f} · **CI:** {result['CI']:.4f} · "
                 f"**CR:** {result['CR']:.4f}")
        st.write("**ELECTRE I üstünlük matrisi**")
        ids = [row["id"] for row in result["filtered_alternatives"]]
        st.caption(f"Eşikler: uyum {result['electre']['concordance_threshold']:.3f}, "
                   f"uyumsuzluk {result['electre']['discordance_threshold']:.3f} "
                   f"({result['electre']['threshold_mode']}).")
        st.dataframe(pd.DataFrame(result["electre"]["outranking_matrix"], index=ids, columns=ids).astype(int),
                     width="stretch")
        st.write("**TOPSIS skorları**")
        st.dataframe(pd.DataFrame(result["final_ranking"])[["rank", "id", "C_star"]],
                     hide_index=True, width="stretch")
        st.download_button("Tam denetim sonucunu JSON indir",
                           json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"),
                           file_name="sarj_karar_audit.json", mime="application/json")


def main():
    st.set_page_config(page_title="Ev şarj cihazı seçimi", layout="centered",
                       initial_sidebar_state="collapsed")
    apply_style()
    st.title("Aracınız için uygun ev şarj cihazını bulun")
    st.write("Aracınız, eviniz ve günlük kullanımınıza göre uygun seçenekleri karşılaştıralım.")
    submitted, inputs, assumptions = get_user_inputs()
    if not submitted:
        show_method()
        show_calculation_details()
        return
    if inputs["home_phase"] == "bilmiyorum":
        st.warning("Kesin teknik uygunluk ve sıralama için evinizin monofaz mı trifaz mı "
                   "olduğunu öğrenin. Elektrik panosu veya bir elektrikçi yardımcı olabilir.")
        show_method()
        show_calculation_details()
        return
    try:
        result = run_decision(inputs, assumptions=assumptions)
    except (ValueError, OSError, ArithmeticError) as error:
        st.error(f"Karar hesaplanamadı: {error}")
        return
    if result["status"] == "no_alternatives":
        st.warning(result["explanation"][0])
        show_method()
        show_calculation_details()
        return
    show_result(result)
    show_method()
    show_calculation_details(result)


if __name__ == "__main__":
    main()
