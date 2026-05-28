import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px

# --- FRAGEN-KONFIGURATION ---
FRAGE_1 = "Wie viele Tassen Kaffee trinkst du täglich?"
FRAGE_2 = "Wieviele Minuten brauchst du von zu Hause ins Büro"

st.set_page_config(layout="wide")

# --- DATENBANK INITIALISIEREN (inklusive Name) ---
def init_db():
    conn = sqlite3.connect("survey_data.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    val_x REAL, 
    val_y REAL
    )
    """)
    conn.commit()
    conn.close()

init_db()

# --- NAVIGATION ---
view = st.sidebar.radio("Ansicht wählen:", ["📱 Teilnehmer: Fragebogen", "📺 Präsentator: Live-Schritt-Demo"])

# ==============================================================================
# VIEW 1: TEILNEHMER-EINGABE
# ==============================================================================
if view == "📱 Teilnehmer: Fragebogen":
    st.title("Inklusive Daten-Eingabe 🗳️")
    st.write("Bitte gib deinen Namen an und beantworte die Fragen:")

with st.form("survey_form", clear_on_submit=True):
# Neues Eingabefeld für den Namen
    user_name = st.text_input("Dein Name / Kürzel:", placeholder="z. B. Anna oder Gast_1")

ans_x = st.slider(FRAGE_1, 1, 10, 5)
ans_y = st.slider(FRAGE_2, 1, 10, 5)
submitted = st.form_submit_button("Antwort absenden")

if submitted:
    if not user_name.strip():
        st.error("Bitte gib einen Namen oder ein Kürzel ein.")
    else:
        conn = sqlite3.connect("survey_data.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO responses (name, val_x, val_y) VALUES (?, ?, ?)", (user_name.strip(), ans_x, ans_y))
        conn.commit()
        conn.close()
        st.success(f"Danke {user_name}! Deine Daten wurden erfolgreich übertragen. Schau auf die Leinwand!")

# ==============================================================================
# VIEW 2: PRÄSENTATOR-LEINWAND
# ==============================================================================
else:
    st.title("🎓 K-Means Clustering: Wer ist in welcher Gruppe?")

# Daten laden (inklusive Name)
conn = sqlite3.connect("survey_data.db")
df = pd.read_sql_query("SELECT name AS Name, val_x AS X, val_y AS Y FROM responses", conn)
conn.close()

# Session State für K-Means initialisieren
if "km_step" not in st.session_state:
    st.session_state.km_step = "init"
if "centroids" not in st.session_state:
    st.session_state.centroids = None
if "assignments" not in st.session_state:
    st.session_state.assignments = None

col_control, col_plot = st.columns([1, 2]) # 1/3 Steuerung, 2/3 Diagramm

with col_control:
    st.subheader("⚙️ Steuerung")
k_value = st.slider("Anzahl der Cluster (k):", min_value=2, max_value=5, value=3)
st.write(f"Teilnehmende Personen: **{len(df)}**")

if len(df) < k_value:
    st.warning(f"Warte auf mindestens {k_value} Teilnehmerpunkte...")
else:
# SCHRITT 1: Zentren initialisieren
    if st.button("1. Zentren zufällig setzen 📍", use_container_width=True):
        np.random.seed(42)
indices = np.random.choice(df.index, size=k_value, replace=False)
st.session_state.centroids = df.iloc[indices][["X", "Y"]].reset_index(drop=True)
st.session_state.assignments = np.zeros(len(df), dtype=int)
st.session_state.km_step = "assigned"

# SCHRITT 2: Punkte zuweisen
disabled_assign = st.session_state.centroids is None or st.session_state.km_step != "moved"
if st.button("2. Punkte dem nächsten Zentrum zuweisen 🔵", use_container_width=True, disabled=disabled_assign):
    for i, row in df.iterrows():
        dists = np.sqrt((st.session_state.centroids["X"] - row["X"])**2 + (st.session_state.centroids["Y"] - row["Y"])**2)
st.session_state.assignments[i] = np.argmin(dists)
st.session_state.km_step = "assigned"

# SCHRITT 3: Zentren verschieben
disabled_move = st.session_state.centroids is None or st.session_state.km_step != "assigned"
if st.button("3. Zentren neu berechnen (Mittelwert) 📐", use_container_width=True, disabled=disabled_move):
    df_temp = df.copy()
df_temp["Cluster"] = st.session_state.assignments
new_centroids = df_temp.groupby("Cluster")[["X", "Y"]].mean().reset_index()
for c in range(k_value):
    if c in new_centroids["Cluster"].values:
        st.session_state.centroids.iloc[c] = new_centroids[new_centroids["Cluster"] == c][["X", "Y"]].iloc[0]
st.session_state.km_step = "moved"

st.write("---")
if st.button("⚠️ Daten & Algorithmus zurücksetzen", use_container_width=True):
    conn = sqlite3.connect("survey_data.db")
cursor = conn.cursor()
cursor.execute("DELETE FROM responses")
conn.commit()
conn.close()
st.session_state.centroids = None
st.session_state.assignments = None
st.session_state.km_step = "init"
st.rerun()

with col_plot:
    if len(df) >= k_value:
        df_plot = df.copy()

if st.session_state.centroids is not None:
    df_plot["Cluster"] = st.session_state.assignments
    df_plot["Cluster_Name"] = "Gruppe " + df_plot["Cluster"].astype(str)

# Zentren für den Plot vorbereiten (ohne echten Personennamen)
    centroids_df = st.session_state.centroids.copy()
    centroids_df["Cluster_Name"] = "ZENTRUM (X)"
    centroids_df["Name"] = "Zentrum"

    plot_all = pd.concat([df_plot, centroids_df], ignore_index=True)
else:
    df_plot["Cluster_Name"] = "Teilnehmerdaten"
    plot_all = df_plot

color_map = {"ZENTRUM (X)": "#000000", "Teilnehmerdaten": "#7f8c8d"}
symbol_map = {"ZENTRUM (X)": "x"}
for c in range(k_value):
    symbol_map[f"Gruppe {c}"] = "circle"

# Plot erstellen – 'hover_name' zeigt den Namen groß an, wenn man drüberfährt
fig = px.scatter(
plot_all, x="X", y="Y", color="Cluster_Name", symbol="Cluster_Name",
hover_name="Name", 
color_discrete_map=color_map, symbol_map=symbol_map,
range_x=[0.5, 10.5], range_y=[0.5, 10.5],
labels={"X": FRAGE_1.split("?")[0], "Y": FRAGE_2.split("?")[0], "Cluster_Name": "Typ"}
)
fig.update_traces(marker=dict(size=16, line=dict(width=1, color='DarkSlateGrey')))
st.plotly_chart(fig, use_container_width=True)

# --- TABELLARISCHE AUSWERTUNG NACH DEM CLUSTERING ---
if len(df) >= k_value and st.session_state.centroids is not None:
    st.write("---")
st.subheader("👥 Wer gehört zu welcher Gruppe?")

# Erstelle Spalten nebeneinander für jedes Cluster
cluster_cols = st.columns(k_value)

for c in range(k_value):
    with cluster_cols[c]:
        st.markdown(f"### 🟢 Gruppe {c}")
# Filter Personen, die diesem Cluster zugeordnet sind
members = df_plot[df_plot["Cluster"] == c]["Name"].tolist()
if members:
    for name in members:
        st.write(f"• {name}")
    else:
        st.write("*Noch keine Personen*")
