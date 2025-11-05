import streamlit as st
import pandas as pd
import plotly.express as px

# Configuration de la page Streamlit pour utiliser toute la largeur
st.set_page_config(layout="wide")

# Titre de l'application
st.title("📊 Analyse Croisée : Précision ETA vs Couverture des Données")
st.markdown("""
Cette application analyse deux ensembles de données :
1.  **Précision des ETA** (`accuracy_detailed_literal.csv`)
2.  **Couverture des données** (`coverage_with_bands.csv`)

L'objectif principal est de **fusionner ces données** pour comprendre si une meilleure couverture des données de suivi (`fractionTrackedExplained`) est corrélée à une meilleure précision des prédictions (`accurate_pct`).
""")

# --- 1. Téléchargement des Fichiers ---
st.sidebar.header("1. Télécharger les fichiers")
f_accuracy = st.sidebar.file_uploader("Fichier Précision (accuracy_detailed_literal.csv)", type="csv")
f_coverage = st.sidebar.file_uploader("Fichier Couverture (coverage_with_bands.csv)", type="csv")

# Condition pour ne démarrer l'analyse que si les deux fichiers sont chargés
if f_accuracy is None or f_coverage is None:
    st.info("Veuillez télécharger les deux fichiers CSV via la barre latérale pour commencer l'analyse.")
    st.stop()

# --- 2. Chargement et Préparation des Données ---
@st.cache_data
def load_data(file_acc, file_cov):
    """Charge, nettoie et fusionne les données."""
    try:
        df_accuracy = pd.read_csv(file_acc)
        df_coverage = pd.read_csv(file_cov)

        # Renommage de la colonne 'route' en 'routeID' dans le fichier de couverture pour permettre la fusion
        df_coverage_renamed = df_coverage.rename(columns={"route": "routeID"})

        # Fusion des deux dataframes
        # Nous utilisons une fusion "left" sur df_accuracy pour conserver sa granularité (par Time Bucket)
        # et y attacher les données de couverture (qui sont par routeID et timePeriod)
        df_merged = pd.merge(
            df_accuracy,
            df_coverage_renamed[['routeID', 'timePeriod', 'fractionTrackedExplained', 'fractionOnFullyMissingTrips']],
            on=['routeID', 'timePeriod'],
            how='left'
        )
        
        # Gestion des cas où une route/période de df_accuracy n'existe pas dans df_coverage
        df_merged['fractionTrackedExplained'] = df_merged['fractionTrackedExplained'].fillna(-1) # Marquer comme "non trouvé"

        return df_accuracy, df_coverage, df_merged

    except Exception as e:
        st.error(f"Erreur lors du chargement ou de la fusion des données : {e}")
        st.stop()

# Chargement des données
df_accuracy, df_coverage, df_merged = load_data(f_accuracy, f_coverage)

# Retirer les données non fusionnées de l'analyse de corrélation
df_corr_analysis = df_merged[df_merged['fractionTrackedExplained'] != -1].copy()


# --- 3. Filtres Interactifs (dans la barre latérale) ---
st.sidebar.header("2. Filtres d'Analyse")

# Filtre pour la période
unique_periods = df_merged['timePeriod'].unique()
selected_periods = st.sidebar.multiselect(
    "Filtrer par Période",
    options=unique_periods,
    default=unique_periods
)

# Filtre pour les lignes (routes)
unique_routes = sorted(df_merged['routeID'].unique())
selected_routes = st.sidebar.multiselect(
    "Filtrer par Ligne (RouteID)",
    options=unique_routes,
    default=unique_routes[:10]  # Par défaut, sélectionner les 10 premières pour éviter la surcharge
)

# Application des filtres sur les dataframes
df_merged_filtered = df_corr_analysis[
    (df_corr_analysis['timePeriod'].isin(selected_periods)) &
    (df_corr_analysis['routeID'].isin(selected_routes))
]

df_acc_filtered = df_accuracy[
    (df_accuracy['timePeriod'].isin(selected_periods)) &
    (df_accuracy['routeID'].isin(selected_routes))
]

df_cov_filtered = df_coverage[
    (df_coverage['timePeriod'].isin(selected_periods)) &
    (df_coverage['route'].isin(selected_routes)) # 'route' ici car c'est le df original
]


# --- 4. Affichage des Analyses (Onglets) ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Analyse Croisée (Synthèse)", 
    "🎯 Analyse de Précision", 
    "📡 Analyse de Couverture", 
    "📄 Données Brutes"
])

# == Onglet 1 : Analyse Croisée (La demande principale) ==
with tab1:
    st.header("Relation entre Couverture et Précision des Prédictions")
    st.write(f"Analyse basée sur **{len(df_merged_filtered)}** points de données (après filtres).")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Corrélation")
        if not df_merged_filtered.empty:
            # Calcul de la corrélation de Pearson
            correlation = df_merged_filtered['fractionTrackedExplained'].corr(df_merged_filtered['accurate_pct'])
            
            st.metric("Corrélation (Couverture vs Précision)", f"{correlation:.2%}")
            
            if correlation > 0.5:
                st.success("Corrélation positive forte : Une meilleure couverture est fortement associée à une meilleure précision.")
            elif correlation > 0.2:
                st.info("Corrélation positive modérée : Une meilleure couverture tend à être associée à une meilleure précision.")
            elif correlation < -0.2:
                st.warning("Corrélation négative : Étonnamment, une meilleure couverture semble liée à une moins bonne précision. À investiguer.")
            else:
                st.info("Pas de corrélation claire (ou faible) : La couverture seule n'explique pas la précision.")
        else:
            st.warning("Aucune donnée à afficher avec les filtres actuels.")

    with col2:
        st.subheader("Synthèse")
        st.markdown("""
        Ce graphique à bulles est le cœur de l'analyse croisée.
        
        * **Axe X (Couverture)** : Le `fractionTrackedExplained` du fichier de couverture.
        * **Axe Y (Précision)** : Le `accurate_pct` du fichier de précision.
        * **Couleur** : Le `Time Bucket` (tranche horaire de prédiction).
        * **Taille** : Le `totalPredictions` pour donner du poids visuel.
        
        **Comment le lire ?** Si les points forment une ligne montante de gauche à droite, cela confirme qu'une meilleure couverture (plus à droite) mène à une meilleure précision (plus haut).
        """)

    # Graphique de l'analyse croisée
    if not df_merged_filtered.empty:
        fig_scatter = px.scatter(
            df_merged_filtered,
            x="fractionTrackedExplained",
            y="accurate_pct",
            color="Time Bucket",
            size="totalPredictions",
            hover_data=['routeID', 'timePeriod'],
            title="Précision (Y) vs Couverture (X) - par Ligne, Période et 'Time Bucket'"
        )
        fig_scatter.update_layout(
            xaxis_title="Taux de Couverture (fractionTrackedExplained)",
            yaxis_title="Taux de Précision (accurate_pct)",
            yaxis_tickformat=".0%"
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("Aucune donnée à afficher pour le graphique de corrélation avec les filtres sélectionnés.")


# == Onglet 2 : Analyse de Précision ==
with tab2:
    st.header("🎯 Analyse Détaillée de la Précision")
    st.write("Cette section explore le fichier `accuracy_detailed_literal.csv`.")
    
    if not df_acc_filtered.empty:
        # Précision moyenne par 'Time Bucket'
        st.subheader("Précision moyenne par 'Time Bucket'")
        df_grouped = df_acc_filtered.groupby('Time Bucket')[['accurate_pct', 'early_pct', 'late_pct']].mean().reset_index()
        fig_acc_timebucket = px.bar(
            df_grouped,
            x='Time Bucket',
            y=['accurate_pct', 'early_pct', 'late_pct'],
            title="Précision moyenne par 'Time Bucket' (toutes lignes/périodes filtrées)",
            labels={"value": "Pourcentage", "variable": "Statut"},
            barmode="group"
        )
        fig_acc_timebucket.update_layout(yaxis_tickformat=".0%")
        st.plotly_chart(fig_acc_timebucket, use_container_width=True)

        # Précision par Ligne
        st.subheader("Précision moyenne par Ligne")
        df_grouped_route = df_acc_filtered.groupby('routeID')['accurate_pct'].mean().reset_index().sort_values(by='accurate_pct', ascending=False)
        fig_acc_route = px.bar(
            df_grouped_route,
            x='routeID',
            y='accurate_pct',
            title="Précision moyenne par Ligne (toutes périodes/buckets filtrés)",
            labels={"routeID": "Ligne", "accurate_pct": "Taux de Précision"}
        )
        fig_acc_route.update_layout(yaxis_tickformat=".0%")
        st.plotly_chart(fig_acc_route, use_container_width=True)
        
    else:
        st.info("Aucune donnée de précision à afficher avec les filtres sélectionnés.")


# == Onglet 3 : Analyse de Couverture ==
with tab3:
    st.header("📡 Analyse Détaillée de la Couverture")
    st.write("Cette section explore le fichier `coverage_with_bands.csv`.")
    
    if not df_cov_filtered.empty:
        # Couverture moyenne par période
        st.subheader("Couverture moyenne par Période")
        df_grouped_period = df_cov_filtered.groupby('timePeriod')['fractionTrackedExplained'].mean().reset_index()
        fig_cov_period = px.bar(
            df_grouped_period,
            x='timePeriod',
            y='fractionTrackedExplained',
            title="Couverture moyenne par Période (toutes lignes filtrées)",
            labels={"timePeriod": "Période", "fractionTrackedExplained": "Taux de Couverture"}
        )
        fig_cov_period.update_layout(yaxis_tickformat=".0%")
        st.plotly_chart(fig_cov_period, use_container_width=True)

        # Couverture par Ligne
        st.subheader("Couverture moyenne par Ligne")
        df_grouped_route_cov = df_cov_filtered.groupby('route')['fractionTrackedExplained'].mean().reset_index().sort_values(by='fractionTrackedExplained', ascending=False)
        fig_cov_route = px.bar(
            df_grouped_route_cov,
            x='route',
            y='fractionTrackedExplained',
            title="Couverture moyenne par Ligne (toutes périodes filtrées)",
            labels={"route": "Ligne", "fractionTrackedExplained": "Taux de Couverture"}
        )
        fig_cov_route.update_layout(yaxis_tickformat=".0%")
        st.plotly_chart(fig_cov_route, use_container_width=True)
    else:
        st.info("Aucune donnée de couverture à afficher avec les filtres sélectionnés.")


# == Onglet 4 : Données Brutes ==
with tab4:
    st.header("📄 Données Brutes et Fusionnées")
    
    st.subheader("Données Fusionnées (utilisées pour l'analyse croisée)")
    st.write(f"Affichage de {len(df_merged_filtered)} lignes (après filtres).")
    st.dataframe(df_merged_filtered)
    
    with st.expander("Afficher les données brutes d'origine (avant fusion et filtres)"):
        st.subheader("Données de Précision (brutes)")
        st.dataframe(df_accuracy.head(1000))
        
        st.subheader("Données de Couverture (brutes)")
        st.dataframe(df_coverage.head(1000))
