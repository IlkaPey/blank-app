# ... (im else-Block, also Präsentator-Ansicht) ...

    with col_control:
        st.subheader("⚙️ Steuerung")
        k_value = st.slider("Anzahl der Cluster (k):", min_value=2, max_value=5, value=3, help="Die Anzahl der Gruppen, die der Algorithmus finden soll.")
        
        st.write(f"Teilnehmende Personen: **{len(df_raw)}**")

        if st.button("➕ Zusätzliche (simulierte) Daten hinzufügen", use_container_width=True):
            generate_and_insert_simulated_data(num_points_per_cluster=5)
            st.rerun()
        
        st.write("---")

        # ... (Funktionen assign_points und move_centroids und convergence_threshold bleiben unverändert) ...

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

        # --- NEU: DATEN EXPORTIEREN MIT/OHNE CLUSTER ---
        if not df_raw.empty:
            df_to_export = df_raw.copy()
            file_name_suffix = ""

            # Checkbox nur anzeigen, wenn Cluster-Zuweisungen verfügbar sind
            cluster_assignments_available = (
                len(st.session_state.assignments) == len(df_raw) and 
                st.session_state.km_step in ["points_assigned", "centroids_moved", "centroids_converged"]
            )

            if cluster_assignments_available:
                include_cluster_in_export = st.checkbox(
                    "Finalen Cluster in Exportdatei einschließen?", 
                    value=True, # Standardmäßig aktiviert, wenn verfügbar
                    help="Fügt eine Spalte mit der zugewiesenen Gruppe (Cluster) hinzu."
                )
            else:
                include_cluster_in_export = False # Kann nicht eingeschlossen werden, wenn nicht vorhanden

            if include_cluster_in_export:
                df_to_export['Finaler Cluster'] = st.session_state.assignments
                # Optional: Cluster-Nummer auf 1-basiert und lesbarer machen
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

# ... (Rest des Codes, d.h. col_plot und tabellarische Auswertung, bleibt unverändert) ...
