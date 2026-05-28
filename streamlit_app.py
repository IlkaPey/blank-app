import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px # <-- Neu: Plotly Express für einfache Scatter Plots
import plotly.graph_objects as go # <-- Neu: Plotly Graph Objects für detaillierte Kontrolle
import random # Für die Farbwahl, falls K höher ist als Standardpaletten

# --- FRAGEN-KONFIGURATION ---
FRAGE_1 = "Wie viele Tassen Kaffee trinkst du täglich?"
FRAGE_2 = "Wieviele Minuten brauchst du von zu Hause ins Büro?"

st.set_page_config(layout="wide")

# --- DATENBANK INITIALISIEREN ---
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

# --- NAVIGATION ---
view = st.sidebar.radio("Ansicht wählen:", ["📱 Teilnehmer: Fragebogen", "📺 Präsentator: Live-Schritt-Demo"])

# ==============================================================================
# VIEW 1: TEILNEHMER-EINGABE
# ==============================================================================
if view == "📱 Teilnehmer: Fragebogen":
    st.title("Inklusive Daten-Eingabe 🗳️")
    st.write("Bitte gib deinen Namen an und beantworte die Fragen:")

    with st.form("survey_form", clear_on_submit=True):
        user_name = st.text_input("Dein Name / Kürzel:", placeholder="z. B. Anna oder Gast_1")
        # Sinnvolle Min/Max-Werte und Schritte für die Fragen
        ans_x = st.slider(FRAGE_1, 0.0, 10.0, 3.0, step=0.5) # Kaffee kann auch 0 sein, halbe Tassen
        ans_y = st.slider(FRAGE_2, 0, 90, 20, step=5)       # Reisezeit in Minuten

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
                st.balloons() # Eine kleine Animation als Feedback


# ==============================================================================
# VIEW 2: PRÄSENTATOR-LEINWAND
# ==============================================================================
else:
    st.title("🎓 K-Means Clustering: Wer ist in welcher Gruppe?")

    # Daten laden (inklusive Name)
    conn = sqlite3.connect("survey_data.db")
    df_raw = pd.read_sql_query("SELECT name AS Name, val_x AS Kaffee, val_y AS Reisezeit FROM responses", conn)
    conn.close()

    # Session State für K-Means initialisieren
    if "km_step" not in st.session_state:
        st.session_state.km_step = "init" # "init", "centroids_set", "points_assigned", "centroids_moved"
    if "centroids" not in st.session_state:
        st.session_state.centroids = pd.DataFrame(columns=["Kaffee", "Reisezeit"])
    if "assignments" not in st.session_state:
        st.session_state.assignments = np.array([])
    if "prev_centroids" not in st.session_state: # Speichert Centroids vom vorherigen Schritt für die Visualisierung der Bewegung
        st.session_state.prev_centroids = pd.DataFrame(columns=["Kaffee", "Reisezeit"])

    col_control, col_plot = st.columns([1, 2]) # 1/3 Steuerung, 2/3 Diagramm

    with col_control:
        st.subheader("⚙️ Steuerung")
        k_value = st.slider("Anzahl der Cluster (k):", min_value=2, max_value=5, value=3, help="Die Anzahl der Gruppen, die der Algorithmus finden soll.")
        
        st.write(f"Teilnehmende Personen: **{len(df_raw)}**")

        if len(df_raw) < k_value:
            st.warning(f"Warte auf mindestens {k_value} Teilnehmerpunkte, um K-Means starten zu können.")
            # Setze km_step zurück, wenn nicht genug Daten
            st.session_state.km_step = "init"
        
        # --- K-Means Schritte ---
        
        # Zentren zufällig setzen
        disabled_init_btn = (len(df_raw) < k_value) or (st.session_state.km_step not in ["init", "centroids_moved"])
        if st.button("1. Zentren zufällig setzen 📍", use_container_width=True, disabled=disabled_init_btn):
            if len(df_raw) >= k_value:
                # np.random.seed(42) # Für reproduzierbare Initialisierung, optional
                indices = np.random.choice(df_raw.index, size=k_value, replace=False)
                st.session_state.centroids = df_raw.loc[indices, ["Kaffee", "Reisezeit"]].reset_index(drop=True)
                st.session_state.assignments = np.zeros(len(df_raw), dtype=int) # Initial keine Zuordnung
                st.session_state.prev_centroids = st.session_state.centroids.copy() # Für den ersten Schritt sind alt und neu gleich
                st.session_state.km_step = "centroids_set"
                st.rerun() # Seite neu laden, um den Zustand zu aktualisieren

        # Punkte zuweisen
        disabled_assign_btn = (st.session_state.km_step != "centroids_set" and st.session_state.km_step != "centroids_moved") or len(df_raw) < k_value
        if st.button("2. Punkte dem nächsten Zentrum zuweisen 🔵", use_container_width=True, disabled=disabled_assign_btn):
            assignments = np.zeros(len(df_raw), dtype=int)
            for i, row in df_raw.iterrows():
                dists = np.sqrt((st.session_state.centroids["Kaffee"] - row["Kaffee"])**2 + (st.session_state.centroids["Reisezeit"] - row["Reisezeit"])**2)
                assignments[i] = np.argmin(dists)
            st.session_state.assignments = assignments
            st.session_state.km_step = "points_assigned"
            st.rerun()

        # Zentren verschieben
        disabled_move_btn = (st.session_state.km_step != "points_assigned") or len(df_raw) < k_value
        if st.button("3. Zentren neu berechnen (Mittelwert) 📐", use_container_width=True, disabled=disabled_move_btn):
            df_temp = df_raw.copy()
            df_temp["Cluster"] = st.session_state.assignments

            new_centroids_data = []
            for c in range(k_value):
                cluster_points = df_temp[df_temp["Cluster"] == c]
                if not cluster_points.empty:
                    new_centroids_data.append(cluster_points[["Kaffee", "Reisezeit"]].mean().to_dict())
                else:
                    # Wenn ein Cluster leer wird, behalte den alten Centroid (oder setze ihn zufällig neu)
                    st.warning(f"Cluster {c} ist leer. Alter Centroid wird beibehalten.")
                    new_centroids_data.append(st.session_state.centroids.iloc[c].to_dict())
            
            st.session_state.prev_centroids = st.session_state.centroids.copy() # Alten Zustand speichern
            st.session_state.centroids = pd.DataFrame(new_centroids_data)
            st.session_state.km_step = "centroids_moved"
            st.rerun()

        st.write("---")
        if st.button("⚠️ Daten & Algorithmus zurücksetzen", use_container_width=True):
            conn = sqlite3.connect("survey_data.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM responses")
            conn.commit()
            conn.close()
            st.session_state.centroids = pd.DataFrame(columns=["Kaffee", "Reisezeit"])
            st.session_state.assignments = np.array([])
            st.session_state.km_step = "init"
            st.session_state.prev_centroids = pd.DataFrame(columns=["Kaffee", "Reisezeit"])
            st.rerun() # Die App komplett neu laden, um den Startzustand zu zeigen


    with col_plot:
        # Hier Plotly-Grafiken integrieren
        
        # Farbpalette für die Cluster (Plotly Express qualitative Palette)
        color_palette = px.colors.qualitative.Plotly
        # Erweitere Palette, falls k_value größer ist als die Standardpalette
        if k_value > len(color_palette):
            extended_palette = color_palette * (k_value // len(color_palette) + 1)
            colors_for_clusters = extended_palette[:k_value]
        else:
            colors_for_clusters = color_palette[:k_value]

        # DataFrame für den Plot vorbereiten
        df_plot = df_raw.copy()
        df_plot["Typ"] = "Teilnehmer" # Standardtyp für Teilnehmer
        df_plot["Cluster"] = -1 # Standardmäßig kein Cluster

        if st.session_state.km_step == "centroids_set":
            title_text = "Schritt 1: Zufällige Centroids gesetzt"
        elif st.session_state.km_step == "points_assigned":
            title_text = "Schritt 2: Punkte den Centroids zugewiesen"
            df_plot["Cluster"] = st.session_state.assignments
            df_plot["Typ"] = df_plot["Cluster"].apply(lambda x: f"Gruppe {x+1}") # Cluster-Namen für Legende
        elif st.session_state.km_step == "centroids_moved":
            title_text = "Schritt 3: Centroids neu berechnet"
            df_plot["Cluster"] = st.session_state.assignments
            df_plot["Typ"] = df_plot["Cluster"].apply(lambda x: f"Gruppe {x+1}") # Cluster-Namen für Legende
        else: # "init" oder nicht genug Daten
            title_text = "Warte auf Teilnehmerdaten oder Starte K-Means"

        # --- Basis-Scatter-Plot (Teilnehmerdaten) ---
        fig = go.Figure()

        if not df_plot.empty:
            # Datenpunkte hinzufügen
            if st.session_state.km_step in ["points_assigned", "centroids_moved"]:
                # Wenn Cluster zugewiesen, färbe nach Cluster
                for cluster_id in range(k_value):
                    cluster_df = df_plot[df_plot["Cluster"] == cluster_id]
                    if not cluster_df.empty:
                        fig.add_trace(go.Scatter(
                            x=cluster_df["Kaffee"],
                            y=cluster_df["Reisezeit"],
                            mode='markers',
                            name=f'Gruppe {cluster_id+1}',
                            marker=dict(size=10, opacity=0.8, color=colors_for_clusters[cluster_id]),
                            hoverinfo='text',
                            hovertext=cluster_df.apply(lambda row: f"Name: {row['Name']}<br>Kaffee: {row['Kaffee']}<br>Reisezeit: {row['Reisezeit']}", axis=1)
                        ))
            else:
                # Ohne Cluster-Zuweisung, alle grau
                fig.add_trace(go.Scatter(
                    x=df_plot["Kaffee"],
                    y=df_plot["Reisezeit"],
                    mode='markers',
                    name='Teilnehmer',
                    marker=dict(size=10, opacity=0.8, color='gray'),
                    hoverinfo='text',
                    hovertext=df_plot.apply(lambda row: f"Name: {row['Name']}<br>Kaffee: {row['Kaffee']}<br>Reisezeit: {row['Reisezeit']}", axis=1)
                ))
            
            # Centroids hinzufügen, wenn vorhanden
            if not st.session_state.centroids.empty:
                for i in range(len(st.session_state.centroids)):
                    current_c = st.session_state.centroids.iloc[i]
                    prev_c = st.session_state.prev_centroids.iloc[i] if not st.session_state.prev_centroids.empty else None

                    # Alte Centroids zeigen, wenn sie sich verschoben haben
                    if st.session_state.km_step == "centroids_moved" and prev_c is not None and \
                       (prev_c["Kaffee"] != current_c["Kaffee"] or prev_c["Reisezeit"] != current_c["Reisezeit"]):
                        fig.add_trace(go.Scatter(
                            x=[prev_c["Kaffee"]],
                            y=[prev_c["Reisezeit"]],
                            mode='markers',
                            marker=dict(symbol='square', size=12, color=colors_for_clusters[i], opacity=0.5, line=dict(width=1, color='Black')),
                            name=f'Alter Centroid {i+1}',
                            hoverinfo='text',
                            hovertext=f'Alter Centroid {i+1}:<br>Kaffee: {prev_c["Kaffee"]:.1f}<br>Reisezeit: {prev_c["Reisezeit"]:.1f}'
                        ))
                        # Eine Linie vom alten zum neuen Centroid, um die Bewegung zu visualisieren
                        fig.add_trace(go.Scatter(
                            x=[prev_c["Kaffee"], current_c["Kaffee"]],
                            y=[prev_c["Reisezeit"], current_c["Reisezeit"]],
                            mode='lines',
                            line=dict(color=colors_for_clusters[i], width=1, dash='dash'),
                            showlegend=False
                        ))

                    # Aktuelle Centroids
                    marker_symbol = 'x' if st.session_state.km_step in ["centroids_set", "points_assigned"] else 'diamond'
                    fig.add_trace(go.Scatter(
                        x=[current_c["Kaffee"]],
                        y=[current_c["Reisezeit"]],
                        mode='markers',
                        marker=dict(symbol=marker_symbol, size=18, color=colors_for_clusters[i], line=dict(width=2, color='Black')),
                        name=f'Centroid {i+1}',
                        hoverinfo='text',
                        hovertext=f'Centroid {i+1}:<br>Kaffee: {current_c["Kaffee"]:.1f}<br>Reisezeit: {current_c["Reisezeit"]:.1f}'
                    ))
        else: # Keine Datenpunkte
            st.info("Bitte warten Sie auf Eingaben von Teilnehmer:innen oder löschen Sie die Daten.")

        fig.update_layout(
            title=title_text,
            xaxis_title=FRAGE_1,
            yaxis_title=FRAGE_2,
            hovermode="closest",
            height=600,
            xaxis=dict(range=[-0.5, 10.5]), # Feste Achsenbereiche für bessere Vergleichbarkeit
            yaxis=dict(range=[-5, 95])
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- TABELLARISCHE AUSWERTUNG NACH DEM CLUSTERING ---
    if len(df_raw) >= k_value and st.session_state.km_step in ["points_assigned", "centroids_moved"]:
        st.write("---")
        st.subheader("👥 Wer gehört zu welcher Gruppe?")

        cluster_cols = st.columns(k_value)

        for c in range(k_value):
            with cluster_cols[c]:
                st.markdown(f"### <span style='color:{colors_for_clusters[c]}'>Gruppe {c+1}</span>", unsafe_allow_html=True)
                # Filter Personen, die diesem Cluster zugeordnet sind
                members = df_raw[st.session_state.assignments == c]["Name"].tolist()
                
                if members:
                    for name in members:
                        st.write(f"• {name}")
                else:
                    st.write("*Noch keine Personen zugeordnet*")
