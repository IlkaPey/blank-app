import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import random # Für np.random.choice und die simulated_data
# qrcode und BytesIO werden nicht mehr benötigt


# --- FRAGEN-KONFIGURATION ---
FRAGE_1 = "Wie viele Tassen Kaffee trinkst du täglich?"
FRAGE_2 = "Wieviele Minuten brauchst du von zu Hause ins Büro?"
FRAGE_2_SKALIERT_LABEL = f"{FRAGE_2} (Skaliert: Original / 10)" 


# --- PRÄSENTATOR PASSWORT ---
# Für Streamlit Cloud: Diesen Wert in .streamlit/secrets.toml speichern:
# presenter_password = "dein_geheimes_passwort"
PRESENTER_PASSWORD = st.secrets.get("presenter_password", "demopassword") # Standardwert für lokale Tests


st.set_page_config(layout="wide")


# --- DATENBANK INITIALISIEREN (SQLite) ---
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

# Datenbank bei jedem App-Start initialisieren
init_db()


# --- FUNKTION: ZUSÄTZLICHE SIMULIERTE DATEN GENERIEREN UND EINFÜGEN (SQLite) ---
def generate_and_insert_simulated_data(num_points_per_cluster=5):
    conn = sqlite3.connect("survey_data.db")
    cursor = conn.cursor()
    
    # Beispiel-Cluster-Zentren für simulierte Daten (unskalierte Originalwerte)
    sim_clusters = [
        {"name_prefix": "Sim_A", "mean_coffee": 1, "mean_commute": 15, "std_coffee": 0.5, "std_commute": 5},
        {"name_prefix": "Sim_B", "mean_coffee": 6, "mean_commute": 20, "std_coffee": 1, "std_commute": 7},
        {"name_prefix": "Sim_C", "mean_coffee": 3, "mean_commute": 50, "std_coffee": 0.8, "std_commute": 10},
    ]
    
    current_max_sim_id = 0
    try:
        cursor.execute("SELECT name FROM responses WHERE name LIKE 'Sim_%' ORDER BY name DESC LIMIT 1")
        res = cursor.fetchone()
        if res and res[0]:
            parts = res[0].split('_')
            if len(parts) > 1 and parts[-1].isdigit():
                current_max_sim_id = int(parts[-1])
    except Exception:
        pass

    sim_data_to_insert = []
    for cluster_info in sim_clusters:
        for i in range(num_points_per_cluster):
            current_max_sim_id += 1 
            name = f"{cluster_info['name_prefix']}_{current_max_sim_id}"
            
            coffee = np.random.normal(cluster_info['mean_coffee'], cluster_info['std_coffee'])
            commute = np.random.normal(cluster_info['mean_commute'], cluster_info['std_commute'])
            
            coffee = max(0, round(coffee))
            commute = max(0, round(commute))

            sim_data_to_insert.append((name, float(coffee), float(commute)))

    cursor.executemany("INSERT INTO responses (name, val_x, val_y) VALUES (?, ?, ?)", sim_data_to_insert)
    conn.commit()
    conn.close()
    st.success(f"{len(sim_data_to_insert)} simulierte Datenpunkte hinzugefügt!")


# --- ROLLEN-MANAGEMENT ---
# Für URL-Parameter-Handling
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode 

query_params = st.query_params
app_role = query_params.get("role", "participant") 

# Initialisiere 'current_selected_view' im Session State für den Präsentator
if "current_selected_view" not in st.session_state:
    st.session_state.current_selected_view = "📱 Teilnehmer: Fragebogen"

# Bestimme die anzuzeigende Ansicht
view = st.session_state.current_selected_view

if app_role == "presenter":
    st.sidebar.title("Präsentator-Login")
    password_input = st.sidebar.text_input("Passwort eingeben:", type="password", key="presenter_pw")
    
    if password_input == PRESENTER_PASSWORD:
        st.sidebar.success("Angemeldet als Präsentator.")
        
        if st.session_state.current_selected_view == "📱 Teilnehmer: Fragebogen":
            st.session_state.current_selected_view = "📺 Präsentator: Live-Schritt-Demo"

        view_options = ["📱 Teilnehmer: Fragebogen", "📺 Präsentator: Live-Schritt-Demo"]
        default_index_for_radio = view_options.index(st.session_state.current_selected_view)

        st.session_state.current_selected_view = st.sidebar.radio(
            "Ansicht wählen:",
            view_options,
            index=default_index_for_radio,
            key="presenter_view_radio"
        )
        view = st.session_state.current_selected_view 

    else:
        st.sidebar.error("Falsches Passwort für Präsentator.")
        app_role = "participant"
        st.session_state.current_selected_view = "📱 Teilnehmer: Fragebogen"
        view = st.session_state.current_selected_view
else:
    view = "📱 Teilnehmer: Fragebogen"


# ==============================================================================
# VIEW 1: TEILNEHMER-EINGABE
# ==============================================================================
if app_role == "participant" or view == "📱 Teilnehmer: Fragebogen":
    st.title("Inklusive Daten-Eingabe 🗳️")
    st.write("Bitte gib deinen Namen an und beantworte die Fragen:")

    with st.form("survey_form", clear_on_submit=True):
        user_name = st.text_input("Dein Name / Kürzel:", placeholder="z. B. Anna oder Gast_1", key="participant_name_input")
        ans_x = st.slider(FRAGE_1, 0, 10, 3, step=1, key="participant_coffee_slider")
        ans_y = st.slider(FRAGE_2, 0, 90, 20, step=5, key="participant_commute_slider")

        submitted = st.form_submit_button("Antwort absenden", key="participant_submit_button")

        if submitted:
            if not user_name.strip():
                st.error("Bitte gib einen Namen oder ein Kürzel ein.")
            else:
                conn = sqlite3.connect("survey_data.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO responses (name, val_x, val_y) VALUES (?, ?, ?)", (user_name.strip(), float(ans_x), float(ans_y)))
                conn.commit()
                conn.close()
                st.success(f"Danke {user_name}! Deine Daten wurden erfolgreich übertragen. Schau auf die Leinwand!")
                st.balloons()


# ==============================================================================
# VIEW 2: PRÄSENTATOR-LEINWAND
# ==============================================================================
if app_role == "presenter" and view == "📺 Präsentator: Live-Schritt-Demo":
    st.title("🎓 K-Means Clustering: Wer ist in welcher Gruppe?")

    # Daten laden (SQLite)
    conn = sqlite3.connect("survey_data.db")
    df_raw = pd.read_sql_query("SELECT name AS Name, val_x AS Kaffee, val_y AS Reisezeit FROM responses", conn)
    conn.close()

    # --- DATEN SKALIEREN für K-Means Berechnungen und Plotting ---
    df_data_for_kmeans = df_raw.copy()
    if not df_data_for_kmeans.empty:
        df_data_for_kmeans['Reisezeit'] = df_data_for_kmeans['Reisezeit'] / 10.0
        df_data_for_kmeans['Kaffee'] = df_data_for_kmeans['Kaffee'].astype(float)
    # -----------------------------------------------------------

    # Session State für K-Means initialisieren
    if "km_step" not in st.session_state:
        st.session_state.km_step = "init"
    if "centroids" not in st.session_state:
        st.session_state.centroids = pd.DataFrame(columns=["Kaffee", "Reisezeit"])
    if "assignments" not in st.session_state:
        st.session_state.assignments = np.array([])
    if "prev_centroids" not in st.session_state:
        st.session_state.prev_centroids = pd.DataFrame(columns=["Kaffee", "Reisezeit"])

    col_control, col_plot = st.columns([1, 2])

    with col_control:
        st.subheader("⚙️ Steuerung")
        k_value = st.slider("Anzahl der Cluster (k):", min_value=2, max_value=5, value=3, help="Die Anzahl der Gruppen, die der Algorithmus finden soll.", key="k_slider")
        
        st.write(f"Teilnehmende Personen: **{len(df_raw)}**")

        # --- Link für Teilnehmer (ohne QR-Code) ---
        st.write("---")
        st.subheader("🔗 Link für Teilnehmer")
        
        # st.get_url() ist die bevorzugte Methode, um die Basis-URL der App zu erhalten
        # Falls es hier einen Fehler gibt (z.B. bei sehr alten Streamlit-Versionen),
        # müsstest du den Link manuell kopieren und einfügen oder diesen Block entfernen.
        try:
            base_url = st.get_url()
        except AttributeError:
            st.warning("`st.get_url()` ist in dieser Streamlit-Version nicht verfügbar. Bitte kopieren Sie die URL aus der Adresszeile des Browsers.")
            base_url = "Ihre_App_URL_hier_einfuegen" # Platzhalter für den Fallback

        parsed_url = urlparse(base_url)
