import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import random # Für np.random.choice und die simulated_data


# --- FRAGEN-KONFIGURATION ---
FRAGE_1 = "Wie viele Tassen Kaffee trinkst du täglich?"
FRAGE_2 = "Wieviele Minuten brauchst du von zu Hause ins Büro?"
FRAGE_2_SKALIERT_LABEL = f"{FRAGE_2} (Skaliert: Original / 10)" 

# --- PRÄSENTATOR PASSWORT (Optional, aber empfohlen für Streamlit Cloud) ---
# Für Streamlit Cloud: Diesen Wert in .streamlit/secrets.toml speichern:
# presenter_password = "mein_geheimes_passwort"
PRESENTER_PASSWORD = st.secrets.get("presenter_password", "clustering") # Standardwert für lokale Tests

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


# --- NEUE FUNKTION: ZUSÄTZLICHE SIMULIERTE DATEN GENERIEREN UND EINFÜGEN ---
def generate_and_insert_simulated_data(num_points_per_cluster=5):
    conn = sqlite3.connect("survey_data.db")
    cursor = conn.cursor()
    
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
    except Exception as e:
        st.warning(f"Fehler beim Ermitteln der max. Sim ID: {e}")
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
query_params = st.query_params
app_role = query_params.get("role", "participant") # Standard: 'participant'

# Initialisiere 'view' Variable für die App-Logik
view = "📱 Teilnehmer: Fragebogen" # Standardwert

if app_role == "presenter":
    st.sidebar.title("Präsentator-Login")
    password_input = st.sidebar.text_input("Passwort eingeben:", type="password", key="presenter_pw")
    
    if password_input == PRESENTER_PASSWORD:
        st.sidebar.success("Angemeldet als Präsentator.")
        view = st.sidebar.radio("Ansicht wählen:", ["📱 Teilnehmer: Fragebogen", "📺 Präsentator: Live-Schritt-Demo"])
    else:
        st.sidebar.error("Falsches Passwort für Präsentator.")
        app_role = "participant" # Fallback auf Teilnehmer-Rolle

# ==============================================================================
# VIEW 1: TEILNEHMER-EINGABE (immer sichtbar für Teilnehmer-Rolle)
# ==============================================================================
if app_role == "participant" or view == "📱 Teilnehmer: Fragebogen": # Teilnehmer sieht immer nur das Formular
    st.title("Inklusive Daten-Eingabe 🗳️")
    st.write("Bitte gib deinen Namen an und beantworte die Fragen:")

    with st.form("survey_form", clear_on_submit=True):
        user_name = st.text_input("Dein Name / Kürzel:", placeholder="z. B. Anna oder Gast_1")
        ans_x = st.slider(FRAGE_1, 0, 10, 3, step=1)
        ans_y = st.slider(FRAGE_2, 0, 90, 20, step=5)

        submitted = st.form_submit_button("Antwort absenden")

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
# VIEW 2: PRÄSENTATOR-LEINWAND (nur sichtbar für Präsentator-Rolle und ausgewählte Ansicht)
# ==============================================================================
if app_role == "presenter" and view == "📺 Präsentator: Live-Schritt-Demo":
    st.title("🎓 K-Means Clustering: Wer ist in welcher Gruppe?")

    # Daten laden (inklusive Name)
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
        k_value = st.slider("Anzahl der Cluster (k):", min_value=2, max_value=5, value=3, help="Die Anzahl der Gruppen, die der Algorithmus finden soll.")
        
        st.write(f"Teilnehmende Personen: **{len(df_raw)}**")

        if st.button("➕ Zusätzliche (simulierte) Daten hinzufügen", use_container_width=True):
            generate_and_insert_simulated_data(num_points_per_cluster=5)
            st.rerun()
        
        st.write("---")

        # --- Funktionen für die K-Means Schritte (nutzen df_data_for_kmeans) ---
        def assign_points():
            if df_data_for_kmeans.empty or st.session_state.centroids.empty:
                st.warning("Keine Daten oder Centroids für Zuweisung verfügbar.")
                return

            assignments = np.zeros(len(df_data_for_kmeans), dtype=int)
            for i, row in df_data_for_kmeans.iterrows():
                dists = np.sqrt((st.session_state.centroids["Kaffee"] - row["Kaffee"])**2 + (st.session_state.centroids["Reisezeit"] - row["Reisezeit"])**2)
                assignments[i] = np.argmin(dists)
            st.session_state.assignments = assignments
            st.session_state.km_step = "points_assigned"
        
        def move_centroids():
            if df_data_for_kmeans.empty or len(st.session_state.assignments) == 0:
                st.warning("Keine Daten oder Zuweisungen für Centroid-Bewegung verfügbar.")
                return

            df_temp_for_calc = df_data_for_kmeans.copy()
            df_temp_for_calc["Cluster"] = st.session_state.assignments

            new_centroids_data = []
            for c in range(k_value):
                cluster_points = df_temp_for_calc[df_temp_for_calc["Cluster"] == c]
                if not cluster_points.empty:
                    new_centroids_data.append(cluster_points[["Kaffee", "Reisezeit"]].mean().to_dict())
                else:
                    st.warning(f"Cluster {c} ist leer. Alter Centroid wird beibehalten.")
                    if not st.session_state.centroids.empty and c < len(st.session_state.centroids):
                        new_centroids_data.append(st.session_state.centroids.iloc[c].to_dict())
                    else:
                        new_centroids_data.append({'Kaffee': np.random.uniform(0, 10), 'Reisezeit': np.random.uniform(0, 9)})
            
            st.session_state.prev_centroids = st.session_state.centroids.copy()
            st.session_state.centroids = pd.DataFrame(new_centroids_data)
            st.session_state.km_step = "centroids_moved"
        
        convergence_threshold = 0.05

        if len(df_data_for_kmeans) < k_value:
            st.warning(f"Warte auf mindestens {k_value} Teilnehmerpunkte, um K-Means starten zu können.")
            st.session_state.km_step = "init"
        
        # --- K-Means Schritte Buttons ---
        
        disabled_init_btn = (len(df_data_for_kmeans) < k_value) or (st.session_state.km_step not in ["init", "centroids_moved", "centroids_converged"])
        if st.button("1. Zentren zufällig setzen 📍", use_container_width=True, disabled=disabled_init_btn):
            if len(df_data_for_kmeans) >= k_value:
                indices = np.random.choice(df_data_for_kmeans.index, size=k_value, replace=False)
                st.session_state.centroids = df_data_for_kmeans.loc[indices, ["Kaffee", "Reisezeit"]].reset_index(drop=True)
                st.session_state.assignments = np.zeros(len(df_data_for_kmeans), dtype=int)
                st.session_state.prev_centroids = st.session_state.centroids.copy()
                st.session_state.km_step = "centroids_set"
                st.rerun()

        disabled_assign_btn = (st.session_state.km_step not in ["centroids_set", "centroids_moved"]) or len(df_data_for_kmeans) < k_value
        if st.button("2. Punkte dem nächsten Zentrum zuweisen 🔵", use_container_width=True, disabled=disabled_assign_btn):
            assign_points()
            st.rerun()

        disabled_move_btn = (st.session_state.km_step != "points_assigned") or len(df_data_for_kmeans) < k_value
        if st.button("3. Zentren neu berechnen (Mittelwert) 📐", use_container_width=True, disabled=disabled_move_btn):
            move_centroids()
            st.rerun()

        st.write("---")

        # --- AUTO-ITERATION BUTTON ---
        disabled_auto_btn = (st.session_state.km_step == "init") or len(df_data_for_kmeans) < k_value
        if st.button("🚀 K-Means automatisch konvergieren lassen", use_container_width=True, disabled=disabled_auto_btn):
            if st.session_state.km_step == "init":
                st.error("Bitte zuerst die Centroids initialisieren (Schritt 1).")
            else:
                iteration_count = 0
                max_iterations = 100 
                
                if st.session_state.km_step == "centroids_set":
                    assign_points()
                
                while True:
                    old_centroids = st.session_state.centroids.copy()
                    move_centroids()
                    
                    if not st.session_state.centroids.empty and not old_centroids.empty:
                        centroids_moved_dist = np.sqrt(((st.session_state.centroids - old_centroids)**2).sum(axis=1)).max()
                    else:
                        centroids_moved_dist = float('inf')

                    if centroids_moved_dist < convergence_threshold or iteration_count >= max_iterations:
                        st.session_state.km_step = "centroids_converged"
                        if centroids_moved_dist < convergence_threshold:
                            st.success(f"K-Means konvergiert nach {iteration_count+1} Iterationen (Bewegung max. {centroids_moved_dist:.2f} skaliert).")
                        else:
                            st.warning(f"K-Means hat maximale Iterationen ({max_iterations}) erreicht, ohne zu konvergieren.")
                        break
                    
                    assign_points()
                    iteration_count += 1
                
                st.rerun()

        st.write("---")

        # --- DATEN EXPORTIEREN MIT/OHNE CLUSTER ---
        if not df_raw.empty:
            df_to_export = df_raw.copy() # Startet mit den Originaldaten

            file_name_suffix = ""

            # Checkbox nur anzeigen, wenn Cluster-Zuweisungen verfügbar sind
            # und die Anzahl der Zuweisungen der aktuellen Anzahl der Rohdatenpunkte entspricht
            cluster_assignments_available = (
                st.session_state.assignments.size > 0 and # Prüft, ob das Array überhaupt Elemente enthält
                st.session_state.assignments.size == len(df_raw) and # WICHTIG: Stimmt die Anzahl der Zuweisungen mit der Anzahl der Datenpunkte überein?
                st.session_state.km_step in ["points_assigned", "centroids_moved", "centroids_converged"]
            )

            # Die Checkbox und die Logik darum herum werden nur ausgeführt, wenn cluster_assignments_available True ist
            include_cluster_in_export = False # Default-Wert, falls Checkbox nicht angezeigt wird
            if cluster_assignments_available:
                # Da st.checkbox einen Wert zurückgibt, muss es immer ausgeführt werden, 
                # wenn die Bedingungen für die Anzeige erfüllt sind.
                include_cluster_in_export = st.checkbox(
                    "Finalen Cluster in Exportdatei einschließen?", 
                    value=True, # Standardmäßig aktiviert, wenn verfügbar
                    help="Fügt eine Spalte mit der zugewiesenen Gruppe (Cluster) hinzu."
                )
            
            if include_cluster_in_export: # Hier prüfen, ob die Checkbox aktiviert ist (oder der Default-True-Fall)
                df_to_export['Finaler Cluster'] = st.session_state.assignments
                df_to_export['Finaler Cluster'] = df_to_export['Finaler Cluster'].apply(lambda x: f"Gruppe {x+1}")
                file_name_suffix = "_mit_cluster"

            csv_data = df_to_export.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"⬇️ Daten{file_name_suffix} als CSV exportieren",
                data=csv_data,
                file_name=f"kmeans_praesentation_daten_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}{file_name_suffix}.csv",
                mime="text/csv",
                use_container_width=True
            )
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
            st.rerun()

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
            st.rerun()


    with col_plot:
        color_palette = px.colors.qualitative.Plotly
        if k_value > len(color_palette):
            extended_palette = color_palette * (k_value // len(color_palette) + 1)
            colors_for_clusters = extended_palette[:k_value]
        else:
            colors_for_clusters = color_palette[:k_value]

        df_plot_for_viz = df_data_for_kmeans.copy()
        df_plot_for_viz["Typ"] = "Teilnehmer"
        df_plot_for_viz["Cluster"] = -1

        title_text = ""
        if st.session_state.km_step == "init":
            title_text = "Warte auf Teilnehmerdaten oder Starte K-Means"
        elif st.session_state.km_step == "centroids_set":
            title_text = "Schritt 1: Zufällige Centroids gesetzt"
        elif st.session_state.km_step == "points_assigned":
            title_text = "Schritt 2: Punkte den Centroids zugewiesen"
            df_plot_for_viz["Cluster"] = st.session_state.assignments
            df_plot_for_viz["Typ"] = df_plot_for_viz["Cluster"].apply(lambda x: f"Gruppe {x+1}")
        elif st.session_state.km_step == "centroids_moved":
            title_text = "Schritt 3: Centroids neu berechnet"
            df_plot_for_viz["Cluster"] = st.session_state.assignments
            df_plot_for_viz["Typ"] = df_plot_for_viz["Cluster"].apply(lambda x: f"Gruppe {x+1}")
        elif st.session_state.km_step == "centroids_converged":
            title_text = "Schritt 4: K-Means konvergiert (optimale Cluster gefunden)"
            df_plot_for_viz["Cluster"] = st.session_state.assignments
            df_plot_for_viz["Typ"] = df_plot_for_viz["Cluster"].apply(lambda x: f"Gruppe {x+1}")


        fig = go.Figure()

        if not df_plot_for_viz.empty:
            if st.session_state.km_step in ["points_assigned", "centroids_moved", "centroids_converged"]:
                for cluster_id in range(k_value):
                    cluster_df = df_plot_for_viz[df_plot_for_viz["Cluster"] == cluster_id]
                    if not cluster_df.empty:
                        original_names_for_hover = df_raw.loc[cluster_df.index, 'Name'].tolist()

                        fig.add_trace(go.Scatter(
                            x=cluster_df["Kaffee"],
                            y=cluster_df["Reisezeit"],
                            mode='markers',
                            name=f'Gruppe {cluster_id+1}',
                            marker=dict(size=10, opacity=0.8, color=colors_for_clusters[cluster_id]),
                            hoverinfo='text',
                            hovertext=[f"Name: {name}<br>Kaffee: {coffee:.1f}<br>Reisezeit: {travel_time*10:.1f} Min (Original)"
                                       for name, coffee, travel_time in zip(original_names_for_hover, cluster_df["Kaffee"], cluster_df["Reisezeit"])]
                        ))
            else:
                fig.add_trace(go.Scatter(
                    x=df_plot_for_viz["Kaffee"],
                    y=df_plot_for_viz["Reisezeit"],
                    mode='markers',
                    name='Teilnehmer',
                    marker=dict(size=10, opacity=0.8, color='gray'),
                    hoverinfo='text',
                    hovertext=[f"Name: {name}<br>Kaffee: {coffee:.1f}<br>Reisezeit: {travel_time*10:.1f} Min (Original)"
                               for name, coffee, travel_time in zip(df_raw["Name"], df_plot_for_viz["Kaffee"], df_plot_for_viz["Reisezeit"])]
                ))
            
            if not st.session_state.centroids.empty:
                for i in range(len(st.session_state.centroids)):
                    current_c = st.session_state.centroids.iloc[i]
                    prev_c = st.session_state.prev_centroids.iloc[i] if not st.session_state.prev_centroids.empty else None

                    if st.session_state.km_step == "centroids_moved" and prev_c is not None and \
                       (prev_c["Kaffee"] != current_c["Kaffee"] or prev_c["Reisezeit"] != current_c["Reisezeit"]):
                        fig.add_trace(go.Scatter(
                            x=[prev_c["Kaffee"]],
                            y=[prev_c["Reisezeit"]],
                            mode='markers',
                            marker=dict(symbol='square', size=12, color=colors_for_clusters[i], opacity=0.5, line=dict(width=1, color='Black')),
                            name=f'Alter Centroid {i+1}',
                            hoverinfo='text',
                            hovertext=f'Alter Centroid {i+1}:<br>Kaffee: {prev_c["Kaffee"]:.1f}<br>Reisezeit: {prev_c["Reisezeit"]*10:.1f} Min (Original)'
                        ))
                        fig.add_trace(go.Scatter(
                            x=[prev_c["Kaffee"], current_c["Kaffee"]],
                            y=[prev_c["Reisezeit"], current_c["Reisezeit"]],
                            mode='lines',
                            line=dict(color=colors_for_clusters[i], width=1, dash='dash'),
                            showlegend=False
                        ))

                    marker_symbol = 'x' if st.session_state.km_step in ["centroids_set", "points_assigned"] else 'diamond'
                    fig.add_trace(go.Scatter(
                        x=[current_c["Kaffee"]],
                        y=[current_c["Reisezeit"]],
                        mode='markers',
                        marker=dict(symbol=marker_symbol, size=18, color=colors_for_clusters[i], line=dict(width=2, color='Black')),
                        name=f'Centroid {i+1}',
                        hoverinfo='text',
                        hovertext=f'Centroid {i+1}:<br>Kaffee: {current_c["Kaffee"]:.1f}<br>Reisezeit: {current_c["Reisezeit"]*10:.1f} Min (Original)'
                    ))
        else:
            st.info("Bitte warten Sie auf Eingaben von Teilnehmer:innen oder fügen Sie simulierte Daten hinzu.")

        fig.update_layout(
            title=title_text,
            xaxis_title=FRAGE_1,
            yaxis_title=FRAGE_2_SKALIERT_LABEL, 
            hovermode="closest",
            height=600,
            xaxis=dict(range=[-0.5, 10.5]),
            yaxis=dict(range=[-0.5, 9.5])
        )
        st.plotly_chart(fig, use_container_width=True)

    if len(df_raw) >= k_value and st.session_state.km_step in ["points_assigned", "centroids_moved", "centroids_converged"]:
        st.write("---")
        st.subheader("👥 Wer gehört zu welcher Gruppe?")

        cluster_cols = st.columns(k_value)

        df_for_avg_calc = df_data_for_kmeans.copy()
        df_for_avg_calc["Cluster"] = st.session_state.assignments

        for c in range(k_value):
            with cluster_cols[c]:
                st.markdown(f"### <span style='color:{colors_for_clusters[c]}'>Gruppe {c+1}</span>", unsafe_allow_html=True)
                
                members_indices = np.where(st.session_state.assignments == c)[0]
                members_names = df_raw.loc[members_indices, "Name"].tolist() # df_raw.loc[members_indices] um den Index korrekt zu verwenden

                if members_names:
                    cluster_data_avg = df_for_avg_calc[df_for_avg_calc["Cluster"] == c]
                    avg_coffee = cluster_data_avg["Kaffee"].mean()
                    avg_commute_scaled = cluster_data_avg["Reisezeit"].mean()

                    st.write(f"Durchschnitt: **{avg_coffee:.1f} Tassen Kaffee**")
                    st.write(f"Durchschnitt: **{avg_commute_scaled*10:.1f} Minuten Reisezeit** (Original)")
                    st.write("---")
                    st.markdown("**Mitglieder:**")
                    for name in members_names:
                        st.write(f"• {name}")
                else:
                    st.write("*Noch keine Personen zugeordnet*")
