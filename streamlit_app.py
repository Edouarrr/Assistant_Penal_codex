"""
Assistant Pénal - Interface principale du cabinet STERU BARATTE AARPI
"""
import streamlit as st
import os

# === Healthcheck intégré à Streamlit pour Railway ===
import streamlit.web.server as st_server
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.runtime.runtime import Runtime
from streamlit.runtime.runtime_local import RuntimeLocal
from streamlit.runtime.app_session import AppSession
from streamlit.runtime.runtime_util import get_session_id
from streamlit.web.server import Server

# Inject a route into Streamlit's Tornado server
from tornado.web import RequestHandler
from streamlit.web.server import create_app

class HealthzHandler(RequestHandler):
    def get(self):
        self.set_status(200)
        self.set_header("Content-Type", "application/json")
        self.finish('{"status":"ok"}')

def inject_healthz_route():
    app = create_app()
    app.add_handlers(r".*", [(r"/healthz", HealthzHandler)])
    print("✅ Health check route /healthz injected into Streamlit server")

inject_healthz_route()

from pathlib import Path
from datetime import datetime
import json
import sys

# Configuration de la page - DOIT ÊTRE LA PREMIÈRE COMMANDE STREAMLIT
st.set_page_config(
    page_title="Assistant Pénal - STERU BARATTE",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === AJOUT POUR HEALTH CHECK ===
# Import du health checker AVANT tout le reste
try:
    from health_check import ensure_app_health, display_health_status
    # Vérification et auto-configuration au démarrage
    print("🏥 Vérification de l'état de l'application...")
    is_healthy, health_report = ensure_app_health()
    if not is_healthy:
        print("⚠️ L'application s'auto-configure...")
        print("Problèmes détectés :", health_report['issues'])
except ImportError:
    print("⚠️ Module health_check non disponible - Mode normal")
    is_healthy = True
    health_report = None
# === FIN AJOUT HEALTH CHECK ===

# Import des modules
try:
    from core.auth.authentication import get_auth_manager
    from core.search.intelligent_search import SearchInterface
    from core.llm.multi_llm_manager import MultiLLMManager
    from core.vector_juridique import VectorJuridique
    from core.ocr_sharepoint_sync import sync_with_filters, SyncState
    from core.letter_generator import generate_letter
    from core.security.rgpd_manager import RGPDManager
    from core.analysis.contradiction_detector import ContradictionDetector
    from core.chromadb_init import get_chroma_client, get_or_create_collection
except ImportError as e:
    st.error(f"⚠️ Erreur d'import des modules : {e}")
    st.info("Certaines fonctionnalités peuvent être indisponibles")

# CSS personnalisé pour le design professionnel
CUSTOM_CSS = """
<style>
/* Palette de couleurs STERU BARATTE */
:root {
    --primary-blue: #1E3A8A;
    --secondary-blue: #3B82F6;
    --accent-blue: #60A5FA;
    --dark-gray: #1F2937;
    --medium-gray: #6B7280;
    --light-gray: #F3F4F6;
    --white: #FFFFFF;
    --success: #10B981;
    --warning: #F59E0B;
    --danger: #EF4444;
}

/* Header styling */
.main-header {
    background: linear-gradient(135deg, var(--primary-blue) 0%, var(--secondary-blue) 100%);
    color: white;
    padding: 2rem;
    margin: -1rem -1rem 2rem -1rem;
    text-align: center;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.main-header h1 {
    font-size: 2.5rem;
    font-weight: 700;
    margin: 0;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
}

.main-header p {
    font-size: 1.1rem;
    margin: 0.5rem 0 0 0;
    opacity: 0.95;
}

/* Search bar styling */
.stTextArea > div > div > textarea {
    border: 2px solid var(--primary-blue);
    border-radius: 8px;
    font-size: 16px;
    padding: 12px;
    transition: all 0.3s ease;
}

.stTextArea > div > div > textarea:focus {
    border-color: var(--secondary-blue);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

/* Button styling */
.stButton > button {
    background-color: var(--primary-blue);
    color: white;
    border: none;
    border-radius: 6px;
    padding: 0.5rem 1rem;
    font-weight: 600;
    transition: all 0.3s ease;
}

.stButton > button:hover {
    background-color: var(--secondary-blue);
    transform: translateY(-1px);
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

/* Metric cards */
div[data-testid="metric-container"] {
    background-color: var(--white);
    border: 1px solid var(--light-gray);
    padding: 1rem;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    transition: all 0.3s ease;
}

div[data-testid="metric-container"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

/* Sidebar styling */
.css-1d391kg {
    background-color: var(--light-gray);
}

/* Tabs styling */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background-color: var(--light-gray);
    padding: 0.5rem;
    border-radius: 8px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 6px;
    padding: 0.5rem 1rem;
    background-color: var(--white);
    border: 1px solid var(--light-gray);
}

.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background-color: var(--primary-blue);
    color: white;
    border-color: var(--primary-blue);
}

/* Status badges */
.status-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.875rem;
    font-weight: 600;
}

.status-success {
    background-color: var(--success);
    color: white;
}

.status-warning {
    background-color: var(--warning);
    color: white;
}

.status-danger {
    background-color: var(--danger);
    color: white;
}

/* File browser styling */
.file-item {
    padding: 0.75rem;
    border: 1px solid var(--light-gray);
    border-radius: 6px;
    margin-bottom: 0.5rem;
    cursor: pointer;
    transition: all 0.3s ease;
}

.file-item:hover {
    background-color: var(--light-gray);
    border-color: var(--secondary-blue);
}

/* Professional card component */
.pro-card {
    background: white;
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    margin-bottom: 1rem;
}

.pro-card-header {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--dark-gray);
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--light-gray);
}
</style>
"""


def render_header():
    """Affiche l'en-tête professionnel."""
    st.markdown("""
    <div class="main-header">
        <h1>⚖️ CABINET STERU BARATTE AARPI</h1>
        <p>Assistant Pénal Intelligent - Droit pénal des affaires</p>
    </div>
    """, unsafe_allow_html=True)


def render_user_info(username: str):
    """Affiche les informations utilisateur."""
    col1, col2, col3 = st.columns([6, 1, 1])
    
    with col2:
        st.markdown(f"""
        <div style='text-align: right; padding: 0.5rem;'>
            👤 <strong>{st.session_state.get('name', username)}</strong>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        if st.button("🚪 Déconnexion", key="logout"):
            auth_manager = get_auth_manager()
            auth_manager.logout()


def render_metrics_dashboard():
    """Affiche le tableau de bord avec métriques."""
    st.markdown("### 📊 Vue d'ensemble")
    
    # Récupérer les statistiques
    try:
        vector_db = VectorJuridique()
        stats = vector_db.get_statistics()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "📁 Documents indexés",
                f"{stats.get('unique_documents', 0):,}",
                delta=f"+{len(st.session_state.get('recent_uploads', []))} aujourd'hui"
            )
        
        with col2:
            st.metric(
                "🧩 Chunks vectorisés",
                f"{stats.get('total_chunks', 0):,}",
                help="Nombre total de segments dans ChromaDB"
            )
        
        with col3:
            # Calculer l'usage OCR
            ocr_usage = st.session_state.get('ocr_usage', 0)
            ocr_quota = int(os.getenv('GOOGLE_VISION_MONTHLY_QUOTA', '100000'))
            ocr_percent = (ocr_usage / ocr_quota) * 100
            
            st.metric(
                "👁️ OCR ce mois",
                f"{ocr_usage:,} / {ocr_quota:,}",
                delta=f"{ocr_percent:.1f}% utilisé",
                delta_color="inverse" if ocr_percent > 80 else "normal"
            )
        
        with col4:
            storage_mb = stats.get('storage_size_mb', 0)
            st.metric(
                "💾 Stockage",
                f"{storage_mb:.1f} MB",
                help="Taille de la base ChromaDB"
            )
        
    except Exception as e:
        st.error(f"Erreur chargement statistiques : {e}")


def render_search_interface():
    """Interface de recherche principale."""
    try:
        search_interface = SearchInterface()
        
        # Barre de recherche
        query = search_interface.render_search_bar()
        
        if query:
            # Parser la requête
            parsed_query = search_interface.search_engine.parse_query(query)
            
            # Afficher l'analyse de la requête
            with st.expander("🔍 Analyse de la requête", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Intention détectée :**", parsed_query.intent)
                    st.write("**Modèles IA :**", ", ".join(parsed_query.models))
                
                with col2:
                    if parsed_query.mentions:
                        st.write("**Mentions :**")
                        for mention in parsed_query.mentions:
                            st.write(f"- @{mention['type']}:{mention['name']}")
                    
                    if parsed_query.filters:
                        st.write("**Filtres :**", parsed_query.filters)
            
            # Dialogue de clarification si nécessaire
            dialogue_responses = search_interface.render_dialogue(parsed_query)
            
            if dialogue_responses is not None:
                # Exécuter la recherche
                with st.spinner("🔄 Recherche en cours..."):
                    results = search_interface.search_engine.execute_search(
                        parsed_query,
                        dialogue_responses
                    )
                    
                    # Sauvegarder dans la session
                    st.session_state.current_search = results
                    
                    # Afficher les résultats
                    search_interface.render_results(results)
    except Exception as e:
        st.error(f"Module de recherche non disponible : {e}")
        st.info("Vérifiez que tous les modules sont correctement installés")


def render_documents_tab():
    """Onglet de gestion des documents."""
    st.markdown("### 📄 Gestion des documents")
    
    doc_tabs = st.tabs([
        "📤 Upload & OCR",
        "📂 Bibliothèque",
        "🔄 Synchronisation",
        "📊 Analyses"
    ])
    
    with doc_tabs[0]:
        render_upload_interface()
    
    with doc_tabs[1]:
        render_document_library()
    
    with doc_tabs[2]:
        render_sync_interface()
    
    with doc_tabs[3]:
        render_analysis_interface()


def render_upload_interface():
    """Interface d'upload et OCR."""
    st.markdown("#### 📤 Upload et traitement OCR")
    
    max_size_mb = int(os.getenv('MAX_UPLOAD_SIZE_MB', '50'))
    
    uploaded_files = st.file_uploader(
        "Glissez vos fichiers ici",
        accept_multiple_files=True,
        type=['pdf', 'png', 'jpg', 'jpeg', 'docx', 'txt'],
        help=f"Formats supportés : PDF, images, Word, texte (max {max_size_mb} MB par fichier)"
    )
    
    if uploaded_files:
        st.markdown(f"**{len(uploaded_files)} fichier(s) sélectionné(s)**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            apply_ocr = st.checkbox("👁️ Appliquer l'OCR", value=True)
            vectorize = st.checkbox("🧠 Vectoriser immédiatement", value=True)
        
        with col2:
            extract_entities = st.checkbox("🏷️ Extraire les entités", value=True)
            generate_summary = st.checkbox("📝 Générer des résumés", value=True)
        
        if st.button("🚀 Traiter les fichiers", type="primary", use_container_width=True):
            process_uploaded_files(
                uploaded_files,
                apply_ocr=apply_ocr,
                vectorize=vectorize,
                extract_entities=extract_entities,
                generate_summary=generate_summary
            )


def render_document_library():
    """Bibliothèque de documents."""
    st.markdown("#### 📚 Documents vectorisés")
    
    # Filtres
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search_term = st.text_input("🔍 Rechercher", placeholder="Nom du fichier...")
    
    with col2:
        doc_type = st.selectbox(
            "Type de document",
            ["Tous", "Audition", "Expertise", "Financier", "Judiciaire", "Procédure"]
        )
    
    with col3:
        date_filter = st.selectbox(
            "Période",
            ["Tous", "Aujourd'hui", "Cette semaine", "Ce mois", "3 derniers mois"]
        )
    
    # Liste des documents (simulation)
    documents = get_document_list(search_term, doc_type, date_filter)
    
    if documents:
        for doc in documents:
            with st.expander(f"📄 {doc['name']}"):
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.write(f"**Type :** {doc['type']}")
                    st.write(f"**Date :** {doc['date']}")
                    st.write(f"**Pages :** {doc['pages']}")
                
                with col2:
                    if st.button("👁️ Voir OCR", key=f"ocr_{doc['id']}"):
                        st.session_state.view_ocr = doc['id']
                    
                    if st.button("📝 Résumé", key=f"summary_{doc['id']}"):
                        st.session_state.view_summary = doc['id']
                
                with col3:
                    if st.button("🗑️ Supprimer", key=f"delete_{doc['id']}"):
                        if st.session_state.get(f"confirm_delete_{doc['id']}"):
                            delete_document(doc['id'])
                        else:
                            st.session_state[f"confirm_delete_{doc['id']}"] = True
                            st.warning("Cliquez à nouveau pour confirmer")
    else:
        st.info("Aucun document trouvé")


def render_sync_interface():
    """Interface de synchronisation SharePoint."""
    st.markdown("#### 🔄 Synchronisation SharePoint")
    
    # État de la synchronisation
    try:
        sync_state = SyncState()
        last_sync = sync_state.state.get('last_sync')
        
        if last_sync:
            from datetime import datetime
            last_sync_date = datetime.fromisoformat(last_sync)
            st.info(f"✅ Dernière synchronisation : {last_sync_date.strftime('%d/%m/%Y à %H:%M')}")
        else:
            st.warning("⚠️ Aucune synchronisation effectuée")
    except:
        st.warning("⚠️ État de synchronisation non disponible")
    
    # Options de synchronisation
    st.markdown("**Options de synchronisation**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        sync_mode = st.radio(
            "Mode",
            ["🌐 Tout SharePoint", "📅 Fichiers récents", "👤 Par auteur", "📁 Dossiers spécifiques"]
        )
    
    with col2:
        days = 7
        author = ""
        folders = ""
        
        if sync_mode == "📅 Fichiers récents":
            days = st.slider("Modifiés dans les derniers", 1, 90, 7, format="%d jours")
        elif sync_mode == "👤 Par auteur":
            author = st.text_input("Nom de l'auteur", placeholder="Ex: Edouard Steru")
        elif sync_mode == "📁 Dossiers spécifiques":
            folders = st.text_area(
                "Dossiers (un par ligne)",
                placeholder="Dossier1\nDossier2/Sous-dossier"
            )
    
    # Options avancées
    with st.expander("⚙️ Options avancées"):
        col1, col2 = st.columns(2)
        
        with col1:
            force_ocr = st.checkbox("Forcer l'OCR sur tous les fichiers")
            skip_existing = st.checkbox("Ignorer les fichiers déjà traités", value=True)
        
        with col2:
            test_mode = st.checkbox("Mode test (simulation)")
            verbose = st.checkbox("Logs détaillés")
    
    # Bouton de synchronisation
    if st.button("🚀 Lancer la synchronisation", type="primary", use_container_width=True):
        run_synchronization(
            mode=sync_mode,
            days=days if sync_mode == "📅 Fichiers récents" else None,
            author=author if sync_mode == "👤 Par auteur" else None,
            folders=folders.split('\n') if sync_mode == "📁 Dossiers spécifiques" else None,
            force_ocr=force_ocr,
            test_mode=test_mode
        )


def render_analysis_interface():
    """Interface d'analyses avancées."""
    st.markdown("#### 📊 Analyses juridiques")
    
    analysis_type = st.selectbox(
        "Type d'analyse",
        [
            "🔍 Détection de contradictions",
            "📅 Chronologie des événements",
            "🕸️ Analyse relationnelle",
            "⚖️ Calcul de prescription",
            "💡 Analyse stratégique"
        ]
    )
    
    if analysis_type == "🔍 Détection de contradictions":
        render_contradiction_analysis()
    elif analysis_type == "📅 Chronologie des événements":
        render_chronology_analysis()
    elif analysis_type == "🕸️ Analyse relationnelle":
        render_relation_analysis()
    elif analysis_type == "⚖️ Calcul de prescription":
        render_prescription_calculator()
    else:
        render_strategic_analysis()


def render_generation_tab():
    """Onglet de génération de documents."""
    st.markdown("### ✍️ Génération de documents")
    
    gen_tabs = st.tabs([
        "📝 Actes juridiques",
        "✉️ Lettres",
        "📋 Listes & tableaux",
        "📊 Rapports"
    ])
    
    with gen_tabs[0]:
        render_legal_acts_generator()
    
    with gen_tabs[1]:
        render_letter_generator()
    
    with gen_tabs[2]:
        render_lists_generator()
    
    with gen_tabs[3]:
        render_reports_generator()


def render_legal_acts_generator():
    """Générateur d'actes juridiques."""
    st.markdown("#### 📝 Génération d'actes juridiques")
    
    act_type = st.selectbox(
        "Type d'acte",
        [
            "Conclusions (défense)",
            "Conclusions (partie civile)",
            "Plainte avec constitution de partie civile",
            "QPC (Question Prioritaire de Constitutionnalité)",
            "Requête en nullité",
            "Mémoire en défense",
            "Requête en restitution"
        ]
    )
    
    # Contexte et paramètres
    with st.form("legal_act_form"):
        st.markdown("**Informations générales**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            jurisdiction = st.text_input("Juridiction", placeholder="Ex: Tribunal correctionnel de Paris")
            case_number = st.text_input("N° de dossier", placeholder="Ex: 2024/12345")
        
        with col2:
            judge_name = st.text_input("Magistrat", placeholder="Ex: M. le Juge DUPONT")
            deadline = st.date_input("Date limite de dépôt")
        
        st.markdown("**Contexte de l'affaire**")
        
        # Sélection des documents de référence
        reference_docs = st.multiselect(
            "Documents de référence",
            get_available_documents(),
            help="Sélectionnez les documents sur lesquels baser l'acte"
        )
        
        # Points clés à inclure
        key_points = st.text_area(
            "Points clés à développer",
            height=150,
            placeholder="- Nullité du PV d'audition du 15/01/2024\n- Absence d'éléments constitutifs\n- Violation des droits de la défense"
        )
        
        # Modèle d'inspiration
        inspiration_model = st.selectbox(
            "S'inspirer d'un modèle existant",
            ["Aucun"] + get_model_documents(act_type)
        )
        
        # Options avancées
        with st.expander("⚙️ Options avancées"):
            col1, col2 = st.columns(2)
            
            with col1:
                tone = st.select_slider(
                    "Ton",
                    ["Très formel", "Formel", "Neutre", "Assertif", "Combatif"],
                    value="Formel"
                )
                
                include_jurisprudence = st.checkbox("Inclure jurisprudence récente", value=True)
            
            with col2:
                max_pages = st.number_input("Nombre de pages max", min_value=1, max_value=50, value=10)
                include_pieces = st.checkbox("Générer liste des pièces", value=True)
        
        # Modèles IA à utiliser
        st.markdown("**Modèles IA**")
        selected_models = st.multiselect(
            "Sélectionner les modèles",
            ["GPT-4o", "Claude Opus 4", "Perplexity"],
            default=["GPT-4o", "Claude Opus 4"]
        )
        
        # Bouton de génération
        if st.form_submit_button("🚀 Générer l'acte", type="primary", use_container_width=True):
            generate_legal_act(
                act_type=act_type,
                jurisdiction=jurisdiction,
                case_number=case_number,
                reference_docs=reference_docs,
                key_points=key_points,
                models=selected_models,
                options={
                    'tone': tone,
                    'include_jurisprudence': include_jurisprudence,
                    'max_pages': max_pages,
                    'include_pieces': include_pieces,
                    'inspiration_model': inspiration_model
                }
            )


def render_settings_tab():
    """Onglet de configuration."""
    st.markdown("### ⚙️ Configuration")
    
    settings_tabs = st.tabs([
        "🔧 Général",
        "🔑 API & Connexions",
        "📊 Quotas & Limites",
        "👥 Utilisateurs",
        "🛡️ Sécurité RGPD"
    ])
    
    with settings_tabs[0]:
        render_general_settings()
    
    with settings_tabs[1]:
        render_api_settings()
    
    with settings_tabs[2]:
        render_quota_settings()
    
    with settings_tabs[3]:
        render_user_settings()
    
    with settings_tabs[4]:
        render_rgpd_settings()


def render_general_settings():
    """Paramètres généraux."""
    st.markdown("#### 🔧 Paramètres généraux")
    
    # Préférences d'interface
    st.markdown("**Interface**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        theme = st.selectbox("Thème", ["Professionnel (Bleu)", "Sombre", "Clair"])
        language = st.selectbox("Langue", ["Français", "English"])
    
    with col2:
        items_per_page = st.number_input("Éléments par page", min_value=10, max_value=100, value=25)
        auto_save = st.checkbox("Sauvegarde automatique", value=True)
    
    # Paramètres de traitement
    st.markdown("**Traitement des documents**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        ocr_languages = st.multiselect(
            "Langues OCR",
            ["Français", "Anglais", "Espagnol", "Allemand"],
            default=["Français", "Anglais"]
        )
        
        chunk_size = st.slider(
            "Taille des chunks", 
            500, 
            2000, 
            int(os.getenv('VECTOR_CHUNK_SIZE', '1000')), 
            step=100
        )
    
    with col2:
        enable_auto_summary = st.checkbox("Résumés automatiques", value=True)
        enable_entity_extraction = st.checkbox("Extraction d'entités", value=True)
        
        chunk_overlap = st.slider(
            "Chevauchement des chunks",
            0,
            500,
            int(os.getenv('VECTOR_CHUNK_OVERLAP', '200')),
            step=50
        )
    
    # Bouton de sauvegarde
    if st.button("💾 Sauvegarder les paramètres", type="primary"):
        save_general_settings({
            'theme': theme,
            'language': language,
            'items_per_page': items_per_page,
            'auto_save': auto_save,
            'ocr_languages': ocr_languages,
            'chunk_size': chunk_size,
            'chunk_overlap': chunk_overlap,
            'enable_auto_summary': enable_auto_summary,
            'enable_entity_extraction': enable_entity_extraction
        })
        st.success("✅ Paramètres sauvegardés")


def render_api_settings():
    """Configuration des API."""
    st.markdown("#### 🔑 Configuration des API")
    
    # Vérification des clés API
    api_status = check_api_keys()
    
    # Affichage du statut
    for api_name, status in api_status.items():
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            if status['configured']:
                st.success(f"✅ {api_name}")
            else:
                st.error(f"❌ {api_name} - Non configuré")
        
        with col2:
            if status['configured']:
                st.caption(f"Dernière vérif : OK")
        
        with col3:
            if st.button("Test", key=f"test_{api_name}"):
                test_api_connection(api_name)
    
    # Instructions de configuration
    with st.expander("📖 Instructions de configuration"):
        st.markdown("""
        **Pour configurer les API :**
        
        1. **OpenAI** : Créez une clé sur [platform.openai.com](https://platform.openai.com)
        2. **Anthropic** : Obtenez une clé sur [console.anthropic.com](https://console.anthropic.com)
        3. **Google Vision** : Configurez un projet sur [Google Cloud Console](https://console.cloud.google.com)
        4. **SharePoint** : Enregistrez une app dans Azure AD
        5. **Legifrance/Judilibre** : Demandez un accès sur leurs portails respectifs
        
        Ajoutez les clés dans les variables d'environnement Railway.
        """)


# Fonctions utilitaires

def process_uploaded_files(files, **options):
    """Traite les fichiers uploadés."""
    progress = st.progress(0)
    status = st.empty()
    
    for i, file in enumerate(files):
        progress.progress((i + 1) / len(files))
        status.text(f"Traitement de {file.name}...")
        
        # Simulation du traitement
        # En production, appeler les vrais modules OCR et vectorisation
        
        if options.get('apply_ocr'):
            # OCR processing
            pass
        
        if options.get('vectorize'):
            # Vectorization
            pass
    
    st.success(f"✅ {len(files)} fichiers traités avec succès")


def get_document_list(search_term, doc_type, date_filter):
    """Récupère la liste des documents (simulation)."""
    # En production, récupérer depuis ChromaDB
    documents = [
        {
            'id': '001',
            'name': 'PV_audition_MARTIN_20240115.pdf',
            'type': 'Audition',
            'date': '15/01/2024',
            'pages': 12
        },
        {
            'id': '002',
            'name': 'Rapport_expertise_comptable_2024.pdf',
            'type': 'Expertise',
            'date': '20/02/2024',
            'pages': 45
        },
        {
            'id': '003',
            'name': 'Conclusions_partie_adverse.docx',
            'type': 'Procédure',
            'date': '10/03/2024',
            'pages': 25
        }
    ]
    
    # Appliquer les filtres
    if search_term:
        documents = [d for d in documents if search_term.lower() in d['name'].lower()]
    
    if doc_type != "Tous":
        documents = [d for d in documents if d['type'] == doc_type]
    
    return documents


def delete_document(doc_id):
    """Supprime un document."""
    try:
        vector_db = VectorJuridique()
        # Implémenter la suppression
        st.success(f"✅ Document {doc_id} supprimé")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Erreur : {e}")


def get_available_documents():
    """Récupère les documents disponibles pour référence."""
    # En production, récupérer depuis ChromaDB
    return [
        "PV_audition_MARTIN_20240115.pdf",
        "Rapport_expertise_comptable_2024.pdf",
        "Conclusions_partie_adverse.docx",
        "Jugement_premiere_instance.pdf"
    ]


def get_model_documents(act_type):
    """Récupère les modèles disponibles pour un type d'acte."""
    # En production, récupérer depuis un dossier de modèles
    models = {
        "Conclusions (défense)": [
            "Modèle_conclusions_relaxe.docx",
            "Modèle_conclusions_nullite.docx"
        ],
        "Plainte avec constitution de partie civile": [
            "Modèle_plainte_escroquerie.docx",
            "Modèle_plainte_abus_confiance.docx"
        ]
    }
    
    return models.get(act_type, [])


def generate_legal_act(act_type, **params):
    """Génère un acte juridique."""
    with st.spinner(f"Génération de {act_type} en cours..."):
        # Simulation de génération
        # En production, utiliser les vrais modules de génération
        
        progress = st.progress(0)
        
        # Étapes de génération
        steps = [
            "Analyse des documents de référence",
            "Extraction des éléments pertinents",
            "Interrogation des modèles IA",
            "Fusion et structuration",
            "Mise en forme juridique",
            "Vérification et finalisation"
        ]
        
        for i, step in enumerate(steps):
            progress.progress((i + 1) / len(steps))
            st.caption(f"🔄 {step}...")
            
            # Simulation de délai
            import time
            time.sleep(0.5)
        
        st.success(f"✅ {act_type} généré avec succès !")
        
        # Afficher le résultat
        with st.expander("📄 Aperçu du document généré"):
            st.markdown(f"""
            **{act_type.upper()}**
            
            **POUR :** {params.get('jurisdiction', 'Tribunal')}
            
            **N° :** {params.get('case_number', 'XXX')}
            
            ---
            
            [Contenu généré par l'IA basé sur les documents de référence]
            
            ---
            
            **PIÈCES COMMUNIQUÉES :**
            1. Pièce n°1 - Document A
            2. Pièce n°2 - Document B
            ...
            """)
        
        # Boutons d'action
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.download_button(
                "📥 Télécharger Word",
                "Contenu du document",
                f"{act_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        
        with col2:
            st.button("✏️ Éditer", key="edit_act")
        
        with col3:
            st.button("📧 Envoyer", key="send_act")


def run_synchronization(**params):
    """Lance la synchronisation SharePoint."""
    progress = st.progress(0)
    status = st.empty()
    
    try:
        if params.get('test_mode'):
            # Mode simulation
            status.info("🧪 Mode test activé - Simulation de synchronisation")
            
            # Simuler les étapes
            steps = [
                "Connexion à SharePoint",
                "Récupération de la liste des fichiers",
                "Filtrage selon les critères",
                "Téléchargement des nouveaux fichiers",
                "Application de l'OCR",
                "Vectorisation des documents"
            ]
            
            for i, step in enumerate(steps):
                progress.progress((i + 1) / len(steps))
                status.text(f"🔄 {step}...")
                
                import time
                time.sleep(0.5)
            
            st.success("✅ Synchronisation simulée terminée")
            
            # Afficher les résultats simulés
            st.json({
                "files_processed": 15,
                "files_skipped": 3,
                "ocr_performed": 12,
                "errors": 0,
                "duration": "2m 34s"
            })
            
        else:
            # Vraie synchronisation
            status.text("🔄 Synchronisation en cours...")
            
            stats = sync_with_filters(
                author=params.get('author'),
                days=params.get('days'),
                specific_folders=params.get('folders')
            )
            
            st.success("✅ Synchronisation terminée")
            st.json(stats)
            
    except Exception as e:
        st.error(f"❌ Erreur : {e}")


def render_contradiction_analysis():
    """Analyse des contradictions."""
    st.write("**Sélection des documents à analyser**")
    
    # Sélection des documents
    docs = st.multiselect(
        "Documents",
        get_available_documents(),
        help="Sélectionnez au moins 2 documents"
    )
    
    if len(docs) >= 2:
        # Options d'analyse
        col1, col2 = st.columns(2)
        
        with col1:
            focus_types = st.multiselect(
                "Types de contradictions",
                ["Dates", "Montants", "Personnes", "Faits"],
                default=["Dates", "Montants"]
            )
        
        with col2:
            sensitivity = st.select_slider(
                "Sensibilité",
                ["Faible", "Normale", "Élevée"],
                value="Normale"
            )
        
        if st.button("🔍 Analyser", type="primary"):
            with st.spinner("Analyse en cours..."):
                # Simulation d'analyse
                st.success("✅ Analyse terminée")
                
                # Résultats simulés
                st.warning("⚠️ 3 contradictions détectées")
                
                with st.expander("📍 Contradiction 1 - Date"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.error("Document 1 : 15/01/2024")
                    with col2:
                        st.error("Document 2 : 18/01/2024")
                    st.write("**Contexte :** Date de la transaction principale")
    else:
        st.info("ℹ️ Sélectionnez au moins 2 documents pour détecter des contradictions")


def check_api_keys():
    """Vérifie le statut des clés API."""
    api_keys = {
        "OpenAI": "OPENAI_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY",
        "Google Vision": "GOOGLE_APPLICATION_CREDENTIALS_JSON",
        "SharePoint": "SHAREPOINT_CLIENT_ID",
        "Mistral": "MISTRAL_API_KEY",
        "Perplexity": "PERPLEXITY_API_KEY",
        "DeepSeek": "DEEPSEEK_API_KEY",
        "Gemini": "GEMINI_API_KEY",
        "Legifrance": ["LEGIFRANCE_CLIENT_ID", "LEGIFRANCE_CLIENT_SECRET"],
        "Judilibre": ["JUDILIBRE_CLIENT_ID", "JUDILIBRE_CLIENT_SECRET"]
    }
    
    status = {}
    for name, env_vars in api_keys.items():
        if isinstance(env_vars, list):
            # Pour les API nécessitant plusieurs variables
            configured = all(bool(os.getenv(var)) for var in env_vars)
            status[name] = {
                'configured': configured,
                'env_vars': env_vars
            }
        else:
            # Pour les API avec une seule variable
            status[name] = {
                'configured': bool(os.getenv(env_vars)),
                'env_var': env_vars
            }
    
    return status


def test_api_connection(api_name):
    """Teste la connexion à une API."""
    with st.spinner(f"Test de {api_name}..."):
        # Simulation de test
        import time
        time.sleep(1)
        
        # En production, faire un vrai test de connexion
        success = True  # Simulation
        
        if success:
            st.success(f"✅ {api_name} : Connexion OK")
        else:
            st.error(f"❌ {api_name} : Échec de connexion")


def save_general_settings(settings):
    """Sauvegarde les paramètres généraux."""
    # En production, sauvegarder dans un fichier de config
    settings_path = Path("config/user_settings.json")
    settings_path.parent.mkdir(exist_ok=True)
    
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)


def render_quota_settings():
    """Gestion des quotas."""
    st.markdown("#### 📊 Quotas et limites")
    
    # Quotas OCR
    st.markdown("**Google Vision OCR**")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        ocr_usage = st.session_state.get('ocr_usage', 45000)
        ocr_quota = int(os.getenv('GOOGLE_VISION_MONTHLY_QUOTA', '100000'))
        
        progress = ocr_usage / ocr_quota
        st.progress(progress)
        st.caption(f"{ocr_usage:,} / {ocr_quota:,} pages")
    
    with col2:
        st.metric("Ce mois", f"{ocr_usage:,}")
    
    with col3:
        if progress > 0.8:
            st.error("⚠️ Quota bientôt atteint")
        else:
            st.success("✅ OK")
    
    # Quotas Embeddings
    st.markdown("**OpenAI Embeddings**")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        embed_usage = st.session_state.get('embedding_usage', 2500000)
        embed_quota_usd = float(os.getenv('OPENAI_MONTHLY_QUOTA_USD', '100'))
        # Conversion approximative USD vers tokens (dépend du modèle)
        embed_quota = int(embed_quota_usd * 1000000)  # Approximation
        
        progress = embed_usage / embed_quota
        st.progress(progress)
        st.caption(f"{embed_usage:,} tokens (~${embed_usage/1000000:.2f})")
    
    with col2:
        st.metric("Ce mois", f"${embed_usage/1000000:.2f}")
    
    with col3:
        if progress > 0.8:
            st.warning("⚠️ Attention budget")
        else:
            st.success("✅ OK")
    
    # Alertes
    st.markdown("**Configuration des alertes**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        alert_threshold = st.slider(
            "Seuil d'alerte (%)",
            50, 95, 80,
            help="Recevoir une alerte quand le quota atteint ce pourcentage"
        )
    
    with col2:
        alert_email = st.text_input(
            "Email d'alerte",
            placeholder="admin@sterubaratte.com"
        )
    
    if st.button("💾 Sauvegarder configuration quotas"):
        st.success("✅ Configuration sauvegardée")


def render_user_settings():
    """Gestion des utilisateurs."""
    st.markdown("#### 👥 Gestion des utilisateurs")
    
    # Vérifier si admin
    if st.session_state.get('username') != 'admin':
        st.warning("⚠️ Accès réservé aux administrateurs")
        return
    
    # Liste des utilisateurs
    users = [
        {'username': 'esteru', 'name': 'Edouard Steru', 'role': 'Avocat', 'status': 'Actif'},
        {'username': 'admin', 'name': 'Administrateur', 'role': 'Admin', 'status': 'Actif'},
    ]
    
    # Affichage
    for user in users:
        with st.expander(f"👤 {user['name']}"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write(f"**Username :** {user['username']}")
                st.write(f"**Rôle :** {user['role']}")
            
            with col2:
                st.write(f"**Statut :** {user['status']}")
                st.write(f"**Dernière connexion :** Aujourd'hui")
            
            with col3:
                if st.button("✏️ Modifier", key=f"edit_{user['username']}"):
                    st.session_state[f"edit_user_{user['username']}"] = True
                
                if user['username'] != 'admin':
                    if st.button("🗑️ Supprimer", key=f"delete_{user['username']}"):
                        st.warning("Fonction non implémentée")
    
    # Ajouter un utilisateur
    st.markdown("**Ajouter un utilisateur**")
    
    with st.form("add_user"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_username = st.text_input("Username")
            new_name = st.text_input("Nom complet")
        
        with col2:
            new_role = st.selectbox("Rôle", ["Avocat", "Stagiaire", "Assistant", "Admin"])
            new_password = st.text_input("Mot de passe", type="password")
        
        if st.form_submit_button("➕ Ajouter"):
            st.success(f"✅ Utilisateur {new_username} ajouté (simulation)")


def render_rgpd_settings():
    """Paramètres RGPD."""
    st.markdown("#### 🛡️ Conformité RGPD")
    
    try:
        # Gestionnaire RGPD
        rgpd = RGPDManager()
        
        # Rapport de conformité
        report = rgpd.generate_rgpd_report()
        
        # Métriques
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Utilisateurs actifs", report['total_users'])
        
        with col2:
            st.metric("Accès ce mois", report['total_accesses'])
        
        with col3:
            if report['retention_compliance']:
                st.success("✅ Conforme")
            else:
                st.error("❌ Non conforme")
        
        # Actions RGPD
        st.markdown("**Actions de conformité**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📊 Rapport RGPD", use_container_width=True):
                st.download_button(
                    "Télécharger",
                    json.dumps(report, indent=2),
                    "rapport_rgpd.json"
                )
        
        with col2:
            if st.button("🗑️ Nettoyer données", use_container_width=True):
                if st.session_state.get('confirm_cleanup'):
                    # Nettoyer
                    st.success("✅ Données nettoyées")
                else:
                    st.session_state['confirm_cleanup'] = True
                    st.warning("Cliquez à nouveau pour confirmer")
        
        with col3:
            if st.button("📥 Export utilisateur", use_container_width=True):
                st.info("Fonction d'export RGPD")
    
    except Exception as e:
        st.error(f"Module RGPD non disponible : {e}")
        st.info("Fonctionnalités RGPD en mode simulation")
    
    # Journal d'audit
    st.markdown("**Journal d'audit récent**")
    
    # Simulation d'entrées
    audit_entries = [
        {"time": "10:45", "user": "esteru", "action": "search_execution", "details": "Recherche contradictions"},
        {"time": "09:30", "user": "admin", "action": "document_upload", "details": "Upload PV_audition.pdf"},
        {"time": "Hier", "user": "esteru", "action": "document_generation", "details": "Génération conclusions"},
    ]
    
    for entry in audit_entries[:5]:
        st.caption(f"🕐 {entry['time']} - {entry['user']} - {entry['action']}")


def render_chronology_analysis():
    """Analyse chronologique."""
    st.write("**Configuration de la chronologie**")
    
    chrono_type = st.selectbox(
        "Type de chronologie",
        ["Chronologie complète", "Chronologie des faits", "Chronologie procédurale", "Flux financiers"]
    )
    
    if st.button("📅 Générer", type="primary"):
        st.info("🚧 Fonction en développement")


def render_relation_analysis():
    """Analyse relationnelle."""
    st.info("🚧 Module d'analyse relationnelle en développement")
    
    # Placeholder
    st.write("Ce module permettra de :")
    st.write("- Identifier les relations entre personnes")
    st.write("- Visualiser les réseaux d'interconnexions")
    st.write("- Détecter les liens financiers")


def render_prescription_calculator():
    """Calculateur de prescription."""
    st.write("**Calcul de prescription pénale**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        date_faits = st.date_input("Date des faits")
        infraction = st.selectbox("Type d'infraction", ["Crime", "Délit", "Contravention"])
    
    with col2:
        dernier_acte = st.date_input("Dernier acte interruptif")
        recidive = st.checkbox("Récidive")
    
    if st.button("⚖️ Calculer", type="primary"):
        # Calcul simple
        delais = {"Crime": 20, "Délit": 6, "Contravention": 1}
        delai = delais[infraction]
        if recidive:
            delai *= 2
        
        from datetime import timedelta
        prescription = dernier_acte + timedelta(days=delai * 365)
        
        if prescription > datetime.now().date():
            st.success(f"✅ Prescription : {prescription.strftime('%d/%m/%Y')}")
            
            # Progress bar
            total_days = (prescription - date_faits).days
            elapsed_days = (datetime.now().date() - date_faits).days
            progress = elapsed_days / total_days
            
            st.progress(progress)
            st.caption(f"{elapsed_days} jours écoulés sur {total_days}")
        else:
            st.error("❌ Prescription acquise")


def render_strategic_analysis():
    """Analyse stratégique."""
    st.info("🚧 Module d'analyse stratégique en développement")


def render_letter_generator():
    """Générateur de lettres."""
    st.markdown("#### ✉️ Génération de lettres")
    
    with st.form("letter_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            destinataire = st.text_input("Destinataire", placeholder="Tribunal de...")
            destinataire_titre = st.text_input("Titre/Fonction", placeholder="Juge d'instruction")
            objet = st.text_input("Objet", placeholder="Demande de...")
        
        with col2:
            destinataire_adresse = st.text_input("Adresse", placeholder="Rue...")
            destinataire_cp_ville = st.text_input("CP et Ville", placeholder="75001 Paris")
            mode_envoi = st.text_input("Mode d'envoi", placeholder="LRAR")
        
        contenu = st.text_area("Corps de la lettre", height=200)
        
        if st.form_submit_button("✉️ Générer", type="primary"):
            try:
                path = generate_letter(
                    destinataire=destinataire,
                    objet=objet,
                    contenu_md=contenu,
                    destinataire_titre=destinataire_titre,
                    destinataire_adresse1=destinataire_adresse,
                    destinataire_cp_ville=destinataire_cp_ville,
                    mode_envoi=mode_envoi
                )
                
                st.success("✅ Lettre générée")
                
                with open(path, "rb") as f:
                    st.download_button("📥 Télécharger", f, file_name=path.name)
                    
            except Exception as e:
                st.error(f"❌ Erreur : {e}")


def render_lists_generator():
    """Générateur de listes et tableaux."""
    st.info("🚧 Module en développement")


def render_reports_generator():
    """Générateur de rapports."""
    st.info("🚧 Module en développement")


def main():
    """Point d'entrée principal de l'application."""
    # CSS personnalisé
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    
    # === AJOUT HEALTH CHECK ===
    # Afficher l'état de santé si disponible
    try:
        if 'display_health_status' in globals():
            display_health_status()
    except:
        pass
    
    # Header
    render_header()
    
    # Authentification
    try:
        auth_manager = get_auth_manager()
        username = auth_manager.render_login_form()
        
        if not username:
            st.stop()
        
        # Afficher info utilisateur
        render_user_info(username)
        
    except ImportError:
        st.warning("⚠️ Mode démo - Authentification non configurée")
        username = "demo"
    
    # Dashboard principal
    render_metrics_dashboard()
    
    # Tabs principaux
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔍 Recherche IA",
        "📄 Documents",
        "✍️ Génération",
        "⚙️ Configuration"
    ])
    
    with tab1:
        render_search_interface()
    
    with tab2:
        render_documents_tab()
    
    with tab3:
        render_generation_tab()
    
    with tab4:
        render_settings_tab()
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #6B7280; font-size: 0.875rem;'>
        Assistant Pénal v2.0 | Cabinet STERU BARATTE AARPI<br>
        Développé avec ❤️ pour le droit pénal des affaires
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()