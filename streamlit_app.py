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
# Für die Achsenbeschriftung und Plots, wenn Reisezeit skaliert ist:
FRAGE_2_SKALIERT_LABEL = f"{FRAGE_2} (Skaliert: Original / 10)" 


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
    
    # Beispiel-Cluster-Zentren für simulierte Daten
    # Diese Werte sind gewählt, um "natürliche" Cluster zu erzeugen
    # Die Werte sind UNskaliert, da sie so in die DB geschrieben werden
    sim_clusters = [
        {"name_prefix": "Sim_A", "mean_coffee": 1, "mean_commute": 15, "std_coffee": 0.5, "std_commute": 5},
        {"name_prefix": "Sim_B", "mean_coffee": 6, "mean_commute": 20, "std_coffee": 1, "std_commute": 7},
        {"name_prefix": "Sim_C", "mean_coffee": 3, "mean_commute": 50, "std_coffee": 0.8, "std_commute": 10},
    ]
    
    # Ermittle die höchste ID von bereits existierenden simulierten Daten
    # um eindeutige Namen zu gewährleisten, z.B. Sim_A_1, Sim_A_2, Sim_B_1, etc.
    current_max_sim_id = 0
    try:
        cursor.execute("SELECT name FROM responses WHERE name LIKE 'Sim_%' ORDER BY name DESC LIMIT 1")
        res = cursor.fetchone()
        if res and res[0]:
            # Extrahieren der Zahl nach dem letzten Unterstrich
            parts = res[0].split('_')
            if len(parts) > 1 and parts[-1].isdigit():
                current_max_sim_id = int(parts[-1])
    except Exception as e:
        # Falls noch keine simulierten Daten oder der Name anders ist
        st.warning(f"Fehler beim Ermitteln der max. Sim ID: {e}")
        pass

    sim_data_to_insert = []
    for cluster_info in sim_clusters:
        for i in range(num_points_per_cluster):
            current_max_sim_id += 1 # Immer weiterzählen, auch über Cluster hinweg, für globale Eindeutigkeit
            name = f"{cluster_info['name_prefix']}_{current_max_sim_id}"
            
            # Generiere Daten mit Normalverteilung um den Mittelwert des Clusters
            coffee = np.random.normal(cluster_info['mean_coffee'], cluster_info['std_coffee'])
            commute = np.random.normal(cluster_info['mean_commute'], cluster_info['std_commute'])
            
            # Sicherstellen, dass Werte nicht negativ sind und ganze Zahlen sind (wie im Formular)
            coffee = max(0, round(coffee)) # Runde auf ganze Tassen
            commute = max(0, round(commute)) # Runde auf ganze Minuten

            sim_data_to_insert.append((name, float(coffee), float(commute))) # Speichern als REAL in DB

    cursor.executemany("INSERT INTO responses (name, val_x, val_y) VALUES (?, ?, ?)", sim_data_to_insert)
    conn.commit()
    conn.close()
    st.success(f"{len(sim_data_to_insert)} simulierte Datenpunkte hinzugefügt!")


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
        # Kaffee Tassen auf ganze Zahlen beschränkt
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
# VIEW 2: PRÄSENTATOR-LEINWAND
# ==============================================================================
else:
    st.title("🎓 K-Means Clustering: Wer ist in welcher Gruppe?")

    # Daten laden (inklusive Name)
    conn = sqlite3.connect("survey_data.db")
    df_raw = pd.read_sql_query("SELECT name AS Name, val_x AS Kaffee, val_y AS Reisezeit FROM responses", conn)
    conn.close()

    # --- DATEN SKALIEREN für K-Means Berechnungen und Plotting ---
    # Die originalen Daten bleiben in df_raw für die Anzeige im Hover-Text etc.
    df_data_for_kmeans = df_raw.copy()
    if not df_data_for_kmeans.empty:
        df_data_for_kmeans['Reisezeit'] = df_data_for_kmeans['Reisezeit'] / 10.0 
        # Sicherstellen, dass Kaffee auch float ist für Konsistenz in Berechnungen
        df_data_for_kmeans['Kaffee'] = df_data_for_kmeans['Kaffee'].astype(float)
    # -----------------------------------------------------------

    # Session State für K-Means initialisieren
    if "km_step" not in st.session_state:
        st.session_state.km_step = "init" # "init", "centroids_set", "points_assigned", "centroids_moved", "centroids_converged"
    if "centroids" not in st.session_state:
        st.session_state.centroids = pd.DataFrame(columns=["Kaffee", "Reisezeit"]) # Centroids speichern skalierte Werte
    if "assignments" not in st.session_state:
        st.session_state.assignments = np.array([])
    if "prev_centroids" not in st.session_state:
        st.session_state.prev_centroids = pd.DataFrame(columns=["Kaffee", "Reisezeit"]) # prev_centroids speichern skalierte Werte

    col_control, col_plot = st.columns([1, 2])

    with col_control:
        st.subheader("⚙️ Steuerung")
        k_value = st.slider("Anzahl der Cluster (k):", min_value=2, max_value=5, value=3, help="Die Anzahl der Gruppen, die der Algorithmus finden soll.")
        
        st.write(f"Teilnehmende Personen: **{len(df_raw)}**")

        if st.button("➕ Zusätzliche (simulierte) Daten hinzufügen", use_container_width=True):
            generate_and_insert_simulated_data(num_points_per_cluster=5) # Fügt 5 Punkte pro simuliertem Cluster hinzu
            st.rerun()
        
        st.write("---")

        # --- Funktionen für die K-Means Schritte (nutzen df_data_for_kmeans) ---
        def assign_points():
            if df_data_for_kmeans.empty or st.session_state.centroids.empty:
                st.warning("Keine Daten oder Centroids für Zuweisung verfügbar.")
                return

            assignments = np.zeros(len(df_data_for_kmeans), dtype=int)
            for i, row in df_data_for_kmeans.iterrows():
                # Centroids sind bereits skaliert, Datenpunkte auch (df_data_for_kmeans)
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
                    # Wenn ein Cluster leer wird, behalte den alten Centroid
                    st.warning(f"Cluster {c} ist leer. Alter Centroid wird beibehalten.")
                    # Sicherstellen, dass der Centroid existiert, bevor darauf zugegriffen wird
                    if not st.session_state.centroids.empty and c < len(st.session_state.centroids):
                        new_centroids_data.append(st.session_state.centroids.iloc[c].to_dict())
                    else: # Falls auch der alte Centroid nicht existiert (sehr unwahrscheinlich), zufällig setzen
                        new_centroids_data.append({'Kaffee': np.random.uniform(0, 10), 'Reisezeit': np.random.uniform(0, 9)})
            
            st.session_state.prev_centroids = st.session_state.centroids.copy() # Zustand VOR der Bewegung
            st.session_state.centroids = pd.DataFrame(new_centroids_data) # NEUE Centroids
            st.session_state.km_step = "centroids_moved"
        
        # Schwellenwert für Konvergenz (passt zur skalierten Reisezeit)
        convergence_threshold = 0.05 # Centroids bewegen sich weniger als 0.05 Einheiten (0.5 Min Original)

        if len(df_data_for_kmeans) < k_value: # Hier df_data_for_kmeans verwenden
            st.warning(f"Warte auf mindestens {k_value} Teilnehmerpunkte, um K-Means starten zu können.")
            st.session_state.km_step = "init"
        
        # --- K-Means Schritte Buttons ---
        
        # 1. Zentren zufällig setzen
        disabled_init_btn = (len(df_data_for_kmeans) < k_value) or (st.session_state.km_step not in ["init", "centroids_moved", "centroids_converged"])
        if st.button("1. Zentren zufällig setzen 📍", use_container_width=True, disabled=disabled_init_btn):
            if len(df_data_for_kmeans) >= k_value:
                indices = np.random.choice(df_data_for_kmeans.index, size=k_value, replace=False)
                st.session_state.centroids = df_data_for_kmeans.loc[indices, ["Kaffee", "Reisezeit"]].reset_index(drop=True)
                st.session_state.assignments = np.zeros(len(df_data_for_kmeans), dtype=int)
                st.session_state.prev_centroids = st.session_state.centroids.copy()
                st.session_state.km_step = "centroids_set"
                st.rerun()

        # 2. Punkte zuweisen
        disabled_assign_btn = (st.session_state.km_step not in ["centroids_set", "centroids_moved"]) or len(df_data_for_kmeans) < k_value
        if st.button("2. Punkte dem nächsten Zentrum zuweisen 🔵", use_container_width=True, disabled=disabled_assign_btn):
            assign_points()
            st.rerun()

        # 3. Zentren verschieben
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
                
                # Wenn wir direkt nach "Zentren setzen" starten, führe die erste Zuweisung hier aus.
                # Wichtig: KEIN st.rerun() hier
                if st.session_state.km_step == "centroids_set":
                    assign_points() # Aktualisiert st.session_state.assignments und km_step
                
                # Jetzt starte den Hauptzyklus
                while True:
                    old_centroids = st.session_state.centroids.copy() # Zustand vor move_centroids()
                    
                    # 1. Centroids verschieben
                    move_centroids() # Aktualisiert st.session_state.centroids und km_step zu "centroids_moved"
                    
                    # 2. Prüfe auf Konvergenz
                    if not st.session_state.centroids.empty and not old_centroids.empty:
                        centroids_moved_dist = np.sqrt(((st.session_state.centroids - old_centroids)**2).sum(axis=1)).max()
                    else: # Falls unerwartet leer, z.B. wenn alle Cluster leer wurden
                        centroids_moved_dist = float('inf')

                    if centroids_moved_dist < convergence_threshold or iteration_count >= max_iterations:
                        st.session_state.km_step = "centroids_converged" # Neuer finaler Zustand
                        if centroids_moved_dist < convergence_threshold:
                            st.success(f"K-Means konvergiert nach {iteration_count+1} Iterationen (Bewegung max. {centroids_moved_dist:.2f} skaliert).")
                        else:
                            st.warning(f"K-Means hat maximale Iterationen ({max_iterations}) erreicht, ohne zu konvergieren.")
                        break # Schleife beenden
                    
                    # 3. Punkte neu zuweisen für die nächste Iteration
                    assign_points() # Aktualisiert st.session_state.assignments und km_step zu "points_assigned"

                    iteration_count += 1
                
                st.rerun() # EINMALIG: App neu laden, um das finale konvergierte Ergebnis zu zeigen

        st.write("---")

        # Daten exportieren
        if not df_raw.empty:
            csv_data = df_raw.to_csv(index=False).encode('utf-8') # Exportiert die ORIGINALEN Daten
            st.download_button(
                label="⬇️ Gesammelte Daten als CSV exportieren",
                data=csv_data,
                file_name=f"kmeans_praesentation_daten_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        st.write("---")

        # Daten & Algorithmus zurücksetzen
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
        # Farbpalette für die Cluster
        color_palette = px.colors.qualitative.Plotly
        if k_value > len(color_palette):
            extended_palette = color_palette * (k_value // len(color_palette) + 1)
            colors_for_clusters = extended_palette[:k_value]
        else:
            colors_for_clusters = color_palette[:k_value]

        # DataFrame für den Plot vorbereiten (nutzt die skalierten Werte)
        df_plot_for_viz = df_data_for_kmeans.copy() # Wichtig: die skalierten Daten für den Plot
        # df_plot_for_viz["Name_Original"] = df_raw["Name"] # Nur wenn df_data_for_kmeans anders sortiert ist
        df_plot_for_viz["Typ"] = "Teilnehmer"
        df_plot_for_viz["Cluster"] = -1

        # Angepasste Titel für den Plot
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


        # --- Basis-Scatter-Plot (Teilnehmerdaten) ---
        fig = go.Figure()

        if not df_plot_for_viz.empty:
            if st.session_state.km_step in ["points_assigned", "centroids_moved", "centroids_converged"]:
                for cluster_id in range(k_value):
                    cluster_df = df_plot_for_viz[df_plot_for_viz["Cluster"] == cluster_id]
                    if not cluster_df.empty:
                        # Originale Namen aus df_raw holen, um sie in den Hover-Text zu packen
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
            else: # Vor der ersten Zuweisung (init, centroids_set)
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
            
            # Centroids hinzufügen, wenn vorhanden (nutzen die skalierten Werte aus st.session_state.centroids)
            if not st.session_state.centroids.empty:
                for i in range(len(st.session_state.centroids)):
                    current_c = st.session_state.centroids.iloc[i]
                    # prev_c ist auch skaliert
                    prev_c = st.session_state.prev_centroids.iloc[i] if not st.session_state.prev_centroids.empty else None

                    # Bewegungslinien und alte Centroids nur zeigen, wenn wir Centroids bewegen
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
                            showlegend=False # Keine Legende für die Bewegungslinie
                        ))

                    # Aktuelle Centroids (nutzen die skalierten Werte)
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
            # y-Achsen-Label verwendet den skalierten Wert, Hover-Text den Originalwert
            yaxis_title=FRAGE_2_SKALIERT_LABEL, 
            hovermode="closest",
            height=600,
            xaxis=dict(range=[-0.5, 10.5]), # Bereich für Kaffee (0-10)
            yaxis=dict(range=[-0.5, 9.5]) # Bereich für Reisezeit (skaliert 0-9)
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- TABELLARISCHE AUSWERTUNG NACH DEM CLUSTERING ---
    # Nur anzeigen, wenn Cluster zugewiesen oder konvergiert sind
    if len(df_raw) >= k_value and st.session_state.km_step in ["points_assigned", "centroids_moved", "centroids_converged"]:
        st.write("---")
        st.subheader("👥 Wer gehört zu welcher Gruppe?")

        cluster_cols = st.columns(k_value)

        # DataFrame für die Durchschnittsberechnung der Cluster (nutzt skalierten df_data_for_kmeans)
        df_for_avg_calc = df_data_for_kmeans.copy()
        df_for_avg_calc["Cluster"] = st.session_state.assignments

        for c in range(k_value):
            with cluster_cols[c]:
                st.markdown(f"### <span style='color:{colors_for_clusters[c]}'>Gruppe {c+1}</span>", unsafe_allow_html=True)
                
                # Mitglieder-Namen direkt aus df_raw holen (unskalierte Original-Daten)
                members_indices = np.where(st.session_state.assignments == c)[0]
                members_names = df_raw.iloc[members_indices]["Name"].tolist()
                
                if members_names:
                    # Durchschnittswerte für diesen Cluster berechnen (aus den skalierten Daten)
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
