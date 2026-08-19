"""
Dashboard Streamlit — przegląd sygnałów cenowych, filtrowanie, trendy.

Uruchomienie: streamlit run dashboard.py
"""

import pandas as pd
import streamlit as st

from database import get_all_signals, init_db
from extraction_agent import PriceSignal, assess_margin_impact, extract_price_signal

st.set_page_config(page_title="Monitor cen surowców opakowaniowych", layout="wide")

init_db()

st.title("Monitor cen surowców opakowaniowych")
st.caption("FA Fin Apps — automatyczne śledzenie zmian cen celulozy, tektury i tworzyw")

signals = get_all_signals()

if not signals:
    st.info(
        "Baza jest pusta. Uruchom `python main.py`, aby pobrać pierwsze dane, "
        "albo dodaj sygnał ręcznie poniżej."
    )
else:
    df = pd.DataFrame(signals)

    col1, col2, col3 = st.columns(3)
    col1.metric("Liczba sygnałów", len(df))
    col2.metric("Podwyżki", int((df["change_type"] == "podwyzka").sum()))
    col3.metric("Obniżki", int((df["change_type"] == "obnizka").sum()))

    materials = ["Wszystkie"] + sorted(df["material"].dropna().unique().tolist())
    selected = st.selectbox("Filtruj wg surowca", materials)

    filtered = df if selected == "Wszystkie" else df[df["material"] == selected]

    st.subheader("Historia sygnałów")
    st.dataframe(
        filtered[
            [
                "announcement_date",
                "material",
                "material_detail",
                "change_type",
                "amount",
                "unit",
                "region",
                "source_company",
                "confidence",
                "summary_pl",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "Pobierz jako CSV",
        filtered.to_csv(index=False).encode("utf-8"),
        file_name="sygnaly_cenowe.csv",
        mime="text/csv",
    )

st.divider()

st.subheader("Analiza ręcznego komunikatu")
st.caption("Wklej tekst komunikatu prasowego, aby agent wyciągnął z niego dane strukturalne.")

manual_text = st.text_area("Tekst komunikatu", height=150)
cost_share = st.slider(
    "Udział tego surowca w koszcie wytworzenia produktu (%)", 0, 100, 50
)

if st.button("Analizuj"):
    if not manual_text.strip():
        st.warning("Wklej najpierw tekst komunikatu.")
    else:
        with st.spinner("Agent analizuje tekst..."):
            try:
                signal = extract_price_signal(manual_text)
            except Exception as e:
                st.error(f"Błąd agenta: {e}")
                signal = None

        if signal is None:
            st.warning("Agent uznał, że tekst nie dotyczy zmiany ceny surowca.")
        else:
            st.success(signal.summary_pl)
            st.json(signal.__dict__)
            margin_note = assess_margin_impact(signal, cost_share)
            st.info(margin_note)
