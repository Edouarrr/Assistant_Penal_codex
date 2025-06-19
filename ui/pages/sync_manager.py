# ui/pages/sync_manager.py
"""Interface Streamlit pour gérer la synchronisation SharePoint."""
import streamlit as st
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Dict, List, Optional
import os

# Import des modules du projet (avec gestion des imports manquants)
try:
    from core.ocr_sharepoint_sync import sync_with_filters, SyncState, GraphClient
    SYNC_AVAILABLE = True
except ImportError:
    SYNC_AVAILABLE = False

def render_sync_page(username: str):
    """Affiche la page de gestion de synchronisation."""
    st.title("🔄 Synchronisation SharePoint")
    
    if not SYNC_AVAILABLE:
        st.error("❌ Module de synchronisation non disponible")
        st.info("Assurez-vous que core/ocr_sharepoint_sync.py est correctement configuré")
        return
    
    # Vérifier les variables d'environnement
    required_vars = ["SHAREPOINT_CLIENT_ID", "SHAREPOINT_CLIENT_SECRET", 
                     "SHAREPOINT_TENANT_ID", "SHAREPOINT_SITE", "SHAREPOINT_DRIVE"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        st.error(f"❌ Variables d'environnement manquantes : {', '.join(missing_vars)}")
        st.info("Configurez ces variables dans Railway pour activer la synchronisation")
        return
    
    # Tabs pour les différentes fonctionnalités
    tab1, tab2, tab3, tab4 = st.tabs([
        "📥 Synchronisation", 
        "📊 État actuel", 
        "⚙️ Configuration",
        "📜 Historique"
    ])
    
    with tab1:
        render_sync_controls()
    
    with tab2:
        render_sync_status()
    
    with tab3:
        render_sync_config()
        
    with tab4:
        render_sync_history()

def render_sync_controls():
    """Contrôles de synchronisation."""
    st.header("🎮 Contrôles de synchronisation")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎯 Synchronisation ciblée")
        
        sync_mode = st.radio(
            "Mode de synchronisation",
            ["🌐 Tout SharePoint", "👤 Par auteur", "📅 Par date", "📁 Dossiers spécifiques"]
        )
        
        author_filter = None
        date_filter = None
        folder_filter = None
        
        if sync_mode == "👤 Par auteur":
            author_filter = st.text_input(
                "Nom de l'auteur",
                placeholder="Ex: Edouard Steru",
                help="Synchronise uniquement les documents créés ou modifiés par cet auteur"
            )
        
        elif sync_mode == "📅 Par date":
            date_filter = st.slider(
                "Documents modifiés dans les derniers",
                min_value=1,
                max_value=365,
                value=30,
                format="%d jours"
            )
        
        elif sync_mode == "📁 Dossiers spécifiques":
            folders_text = st.text_area(
                "Dossiers à synchroniser (un par ligne)",
                placeholder="Dossier1\nDossier2/Sous-dossier\nDossier3",
                height=100
            )
            if folders_text:
                folder_filter = [f.strip() for f in folders_text.split('\n') if f.strip()]
        
        # Options avancées
        with st.expander("⚙️ Options avancées"):
            force_ocr = st.checkbox("Forcer l'OCR même sur les fichiers déjà traités")
            skip_vectorization = st.checkbox("Ignorer la vectorisation (OCR uniquement)")
            dry_run = st.checkbox("Mode simulation (affiche ce qui serait fait sans l'exécuter)")
        
        # Bouton de lancement
        if st.button("🚀 Lancer la synchronisation", type="primary", use_container_width=True):
            with st.spinner("Synchronisation en cours..."):
                progress_placeholder = st.empty()
                status_placeholder = st.empty()
                
                try:
                    # Simulation de progression (à remplacer par la vraie progression)
                    progress_bar = progress_placeholder.progress(0, text="Initialisation...")
                    
                    if dry_run:
                        # Mode simulation
                        status_placeholder.info("🔍 Mode simulation activé")
                        st.write("**Actions qui seraient effectuées :**")
                        
                        # Simuler la liste des fichiers
                        if sync_mode == "🌐 Tout SharePoint":
                            st.write("- Synchronisation de tous les fichiers")
                        elif sync_mode == "👤 Par auteur" and author_filter:
                            st.write(f"- Filtrage par auteur : {author_filter}")
                        elif sync_mode == "📅 Par date" and date_filter:
                            st.write(f"- Fichiers des {date_filter} derniers jours")
                        elif sync_mode == "📁 Dossiers spécifiques" and folder_filter:
                            st.write(f"- Dossiers : {', '.join(folder_filter)}")
                        
                        progress_bar.progress(100, text="Simulation terminée")
                    else:
                        # Vraie synchronisation
                        stats = sync_with_filters(
                            author=author_filter if sync_mode == "👤 Par auteur" else None,
                            days=date_filter if sync_mode == "📅 Par date" else None,
                            specific_folders=folder_filter if sync_mode == "📁 Dossiers spécifiques" else None
                        )
                        
                        progress_bar.progress(100, text="Synchronisation terminée")
                        
                        # Afficher les résultats
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("📄 Fichiers traités", stats.get('files_processed', 0))
                        with col2:
                            st.metric("⏭️ Fichiers ignorés", stats.get('files_skipped', 0))
                        with col3:
                            st.metric("👁️ OCR effectués", stats.get('ocr_performed', 0))
                        with col4:
                            st.metric("❌ Erreurs", stats.get('errors', 0))
                        
                        if stats.get('errors', 0) > 0:
                            st.warning(f"⚠️ {stats['errors']} erreurs rencontrées. Consultez les logs.")
                        else:
                            st.success("✅ Synchronisation terminée avec succès!")
                        
                        # Sauvegarder dans l'historique
                        save_sync_history(sync_mode, stats, author_filter, date_filter, folder_filter)
                        
                except Exception as e:
                    st.error(f"❌ Erreur lors de la synchronisation : {str(e)}")
                    progress_bar.progress(0, text="Erreur")
    
    with col2:
        st.subheader("🧪 Tests et diagnostics")
        
        # Test de connexion
        if st.button("🔌 Tester la connexion SharePoint"):
            with st.spinner("Test en cours..."):
                try:
                    client = GraphClient()
                    # Tester la connexion en récupérant la racine
                    test_result = client._headers()
                    if test_result.get('Authorization'):
                        st.success("✅ Connexion SharePoint OK")
                        st.json({
                            "Site ID": os.getenv("SHAREPOINT_SITE"),
                            "Drive ID": os.getenv("SHAREPOINT_DRIVE"),
                            "Statut": "Connecté"
                        })
                    else:
                        st.error("❌ Impossible de se connecter")
                except Exception as e:
                    st.error(f"❌ Erreur de connexion : {str(e)}")
        
        # Test OCR sur un fichier
        st.markdown("---")
        uploaded_file = st.file_uploader(
            "Tester l'OCR sur un fichier",
            type=['pdf', 'png', 'jpg', 'jpeg'],
            help="Upload un fichier pour tester l'OCR Google Vision"
        )
        
        if uploaded_file and st.button("🔍 Lancer le test OCR"):
            with st.spinner("OCR en cours..."):
                try:
                    # Sauvegarder temporairement le fichier
                    temp_path = Path(f"temp_{uploaded_file.name}")
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Importer et utiliser _ocr_file
                    from core.ocr_sharepoint_sync import _ocr_file
                    text = _ocr_file(temp_path)
                    
                    # Nettoyer
                    temp_path.unlink()
                    
                    # Afficher le résultat
                    st.success("✅ OCR terminé!")
                    with st.expander("📝 Texte extrait"):
                        st.text_area("Résultat OCR", text, height=300)
                    
                    # Statistiques
                    st.metric("Caractères extraits", len(text))
                    st.metric("Mots détectés", len(text.split()))
                    
                except Exception as e:
                    st.error(f"❌ Erreur OCR : {str(e)}")
                    if temp_path.exists():
                        temp_path.unlink()

def render_sync_status():
    """Affiche l'état actuel de la synchronisation."""
    st.header("📊 État de la synchronisation")
    
    try:
        sync_state = SyncState()
        state = sync_state.state
        
        # Métriques générales
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📄 Fichiers synchronisés", len(state.get('processed_files', {})))
        with col2:
            last_sync = state.get('last_sync')
            if last_sync:
                last_sync_date = datetime.fromisoformat(last_sync)
                delta = datetime.now() - last_sync_date
                st.metric("⏱️ Dernière sync", f"Il y a {delta.days}j {delta.seconds//3600}h")
            else:
                st.metric("⏱️ Dernière sync", "Jamais")
        with col3:
            st.metric("🗑️ Fichiers supprimés détectés", len(state.get('deleted_files', [])))
        
        # Fichiers récemment traités
        st.subheader("📑 Fichiers récemment synchronisés")
        processed_files = state.get('processed_files', {})
        if processed_files:
            # Trier par date de modification
            recent_files = sorted(
                processed_files.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]  # Les 10 plus récents
            
            for file_id, modified_date in recent_files:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"📄 {file_id[:50]}...")
                with col2:
                    try:
                        date = datetime.fromisoformat(modified_date)
                        st.text(date.strftime("%d/%m/%Y %H:%M"))
                    except:
                        st.text(modified_date)
        else:
            st.info("Aucun fichier synchronisé pour le moment")
        
        # Fichiers supprimés
        if state.get('deleted_files'):
            with st.expander("🗑️ Fichiers supprimés détectés"):
                for deletion in state['deleted_files'][-10:]:  # Les 10 derniers
                    st.write(f"- {deletion['id']} (supprimé le {deletion['deletion_date']})")
        
    except Exception as e:
        st.error(f"❌ Impossible de charger l'état : {str(e)}")

def render_sync_config():
    """Configuration de la synchronisation."""
    st.header("⚙️ Configuration")
    
    # Quotas et limites
    st.subheader("📊 Gestion des quotas")
    
    col1, col2 = st.columns(2)
    with col1:
        ocr_quota = st.number_input(
            "Quota mensuel Google Vision (pages)",
            min_value=1000,
            max_value=1000000,
            value=100000,
            step=1000,
            help="Nombre maximum de pages à OCRiser par mois"
        )
        
        current_usage = st.session_state.get('ocr_usage', 0)
        st.progress(current_usage / ocr_quota, text=f"{current_usage:,} / {ocr_quota:,} pages")
        
        if current_usage > ocr_quota * 0.9:
            st.warning("⚠️ Quota OCR bientôt atteint!")
    
    with col2:
        embedding_quota = st.number_input(
            "Quota mensuel OpenAI Embeddings",
            min_value=10000,
            max_value=10000000,
            value=1000000,
            step=10000,
            help="Nombre maximum de tokens à vectoriser par mois"
        )
        
        current_embedding = st.session_state.get('embedding_usage', 0)
        st.progress(current_embedding / embedding_quota, text=f"{current_embedding:,} / {embedding_quota:,} tokens")
    
    # Planification automatique
    st.subheader("🕐 Synchronisation automatique")
    
    auto_sync = st.checkbox("Activer la synchronisation automatique")
    
    if auto_sync:
        col1, col2 = st.columns(2)
        with col1:
            sync_frequency = st.selectbox(
                "Fréquence",
                ["Toutes les heures", "Toutes les 4 heures", "Quotidienne", "Hebdomadaire"]
            )
        with col2:
            sync_time = st.time_input(
                "Heure de synchronisation",
                value=datetime.strptime("02:00", "%H:%M").time()
            )
        
        st.info(f"🔄 Prochaine synchronisation : {sync_time.strftime('%H:%M')}")
    
    # Filtres permanents
    st.subheader("🔍 Filtres par défaut")
    
    exclude_patterns = st.text_area(
        "Patterns à exclure (un par ligne)",
        value="*.tmp\n~$*\n.DS_Store",
        help="Fichiers à ignorer lors de la synchronisation"
    )
    
    min_file_size = st.number_input(
        "Taille minimale des fichiers (Ko)",
        min_value=0,
        value=10,
        help="Ignorer les fichiers plus petits que cette taille"
    )
    
    if st.button("💾 Sauvegarder la configuration"):
        config = {
            'ocr_quota': ocr_quota,
            'embedding_quota': embedding_quota,
            'auto_sync': auto_sync,
            'sync_frequency': sync_frequency if auto_sync else None,
            'sync_time': sync_time.strftime('%H:%M') if auto_sync else None,
            'exclude_patterns': exclude_patterns.split('\n'),
            'min_file_size': min_file_size
        }
        
        save_sync_config(config)
        st.success("✅ Configuration sauvegardée!")

def render_sync_history():
    """Affiche l'historique des synchronisations."""
    st.header("📜 Historique des synchronisations")
    
    history = load_sync_history()
    
    if not history:
        st.info("Aucune synchronisation effectuée pour le moment")
        return
    
    # Graphique de l'historique
    if len(history) > 1:
        import plotly.graph_objects as go
        
        dates = [h['timestamp'] for h in history]
        files_processed = [h['stats'].get('files_processed', 0) for h in history]
        ocr_performed = [h['stats'].get('ocr_performed', 0) for h in history]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=files_processed,
            mode='lines+markers',
            name='Fichiers traités',
            line=dict(color='blue')
        ))
        fig.add_trace(go.Scatter(
            x=dates, y=ocr_performed,
            mode='lines+markers',
            name='OCR effectués',
            line=dict(color='green')
        ))
        
        fig.update_layout(
            title="Évolution des synchronisations",
            xaxis_title="Date",
            yaxis_title="Nombre",
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Tableau détaillé
    st.subheader("📋 Détails des synchronisations")
    
    for entry in reversed(history[-10:]):  # Les 10 dernières
        with st.expander(f"🕐 {entry['timestamp']} - {entry['mode']}"):
            col1, col2, col3, col4 = st.columns(4)
            
            stats = entry['stats']
            with col1:
                st.metric("Fichiers traités", stats.get('files_processed', 0))
            with col2:
                st.metric("Fichiers ignorés", stats.get('files_skipped', 0))
            with col3:
                st.metric("OCR effectués", stats.get('ocr_performed', 0))
            with col4:
                st.metric("Erreurs", stats.get('errors', 0))
            
            # Détails des filtres
            if entry.get('filters'):
                st.write("**Filtres appliqués :**")
                filters = entry['filters']
                if filters.get('author'):
                    st.write(f"- Auteur : {filters['author']}")
                if filters.get('days'):
                    st.write(f"- Fichiers des {filters['days']} derniers jours")
                if filters.get('folders'):
                    st.write(f"- Dossiers : {', '.join(filters['folders'])}")

# Fonctions utilitaires

def save_sync_history(mode: str, stats: Dict, author: str = None, days: int = None, folders: List[str] = None):
    """Sauvegarde l'historique de synchronisation."""
    history_file = Path("sync_history.json")
    
    history = load_sync_history()
    
    entry = {
        'timestamp': datetime.now().isoformat(),
        'mode': mode,
        'stats': stats,
        'filters': {
            'author': author,
            'days': days,
            'folders': folders
        }
    }
    
    history.append(entry)
    
    # Garder seulement les 100 dernières entrées
    history = history[-100:]
    
    with open(history_file, 'w') as f:
        json.dump(history, f, indent=2)

def load_sync_history() -> List[Dict]:
    """Charge l'historique de synchronisation."""
    history_file = Path("sync_history.json")
    
    if history_file.exists():
        with open(history_file, 'r') as f:
            return json.load(f)
    
    return []

def save_sync_config(config: Dict):
    """Sauvegarde la configuration de synchronisation."""
    config_file = Path("sync_config.json")
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

def load_sync_config() -> Dict:
    """Charge la configuration de synchronisation."""
    config_file = Path("sync_config.json")
    
    if config_file.exists():
        with open(config_file, 'r') as f:
            return json.load(f)
    
    return {}

# Export de la fonction principale
__all__ = ['render_sync_page']
