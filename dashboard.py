"""
Dashboard Streamlit — przegląd sygnałów cenowych, filtrowanie, trendy.

Uruchomienie: streamlit run dashboard.py
"""

import pandas as pd
import streamlit as st

from database import get_all_signals, get_token_usage_log, get_token_usage_summary, init_db
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
                signal = extract_price_signal(manual_text, process_name="ekstrakcja_reczna")
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

st.divider()

st.subheader("Zużycie tokenów")
st.caption("Podział wg procesu/czynności — tokeny wejściowe, wyjściowe i myślenia (reasoning)")

summary = get_token_usage_summary()

if not summary:
    st.info("Brak jeszcze zarejestrowanego zużycia tokenów.")
else:
    summary_df = pd.DataFrame(summary)

    total_input = int(summary_df["suma_wejsciowych"].sum())
    total_output = int(summary_df["suma_wyjsciowych"].sum())
    total_reasoning = int(summary_df["suma_myslenia"].sum())
    total_calls = int(summary_df["wywolania"].sum())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Wywołania API", total_calls)
    m2.metric("Tokeny wejściowe", f"{total_input:,}".replace(",", " "))
    m3.metric("Tokeny wyjściowe", f"{total_output:,}".replace(",", " "))
    m4.metric("Tokeny myślenia", f"{total_reasoning:,}".replace(",", " "))

    st.markdown("**Podział wg procesu i modelu**")
    display_df = summary_df.rename(
        columns={
            "process": "proces",
            "model": "model",
            "wywolania": "wywołania",
            "suma_wejsciowych": "wejściowe",
            "suma_wyjsciowych": "wyjściowe",
            "suma_myslenia": "myślenie",
            "suma_calkowita": "razem",
        }
    )
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    chart_df = summary_df.melt(
        id_vars=["process"],
        value_vars=["suma_wejsciowych", "suma_wyjsciowych", "suma_myslenia"],
        var_name="typ",
        value_name="tokeny",
    )
    chart_df["typ"] = chart_df["typ"].map(
        {
            "suma_wejsciowych": "wejściowe",
            "suma_wyjsciowych": "wyjściowe",
            "suma_myslenia": "myślenie",
        }
    )
    st.bar_chart(chart_df, x="process", y="tokeny", color="typ", stack=True)

    with st.expander("Pokaż surowy log ostatnich wywołań"):
        log_df = pd.DataFrame(get_token_usage_log(limit=200))
        st.dataframe(log_df, use_container_width=True, hide_index=True)
