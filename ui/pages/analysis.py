# ui/pages/analysis.py
"""Page d'analyse juridique avec détection de contradictions."""
import streamlit as st
from datetime import datetime
from typing import List, Dict, Any
import json

# Import des modules d'analyse
try:
    from core.analysis.contradiction_detector import ContradictionDetector
    CONTRADICTION_DETECTOR_AVAILABLE = True
except ImportError:
    CONTRADICTION_DETECTOR_AVAILABLE = False
    st.warning("⚠️ Module de détection de contradictions non disponible")

# Import du gestionnaire multi-LLM
try:
    from core.llm.multi_llm_manager import MultiLLMManager
    MULTI_LLM_AVAILABLE = True
except ImportError:
    MULTI_LLM_AVAILABLE = False


def render_analysis_page(username: str):
    """Page principale d'analyse juridique."""
    st.title("📊 Analyses juridiques avancées")
    
    # Onglets pour différents types d'analyses
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔍 Contradictions",
        "📅 Chronologie",
        "🔗 Relations",
        "⚖️ Prescription",
        "💡 Stratégie"
    ])
    
    with tab1:
        render_contradiction_analysis()
    
    with tab2:
        render_chronology_analysis()
    
    with tab3:
        render_relation_analysis()
    
    with tab4:
        render_prescription_calculator()
    
    with tab5:
        render_strategy_analysis()


def render_contradiction_analysis():
    """Interface pour la détection de contradictions."""
    st.header("🔍 Détection de contradictions")
    
    if not CONTRADICTION_DETECTOR_AVAILABLE:
        st.error("❌ Le module de détection n'est pas installé")
        return
    
    # Sélection des documents
    st.markdown("### 1. Sélectionner les documents à analyser")
    
    # Simuler une liste de documents
    available_docs = [
        "PV_audition_MARTIN_15012025.pdf",
        "PV_audition_MARTIN_20012025.pdf",
        "PV_confrontation_MARTIN_DURAND.pdf",
        "Rapport_expertise_comptable.pdf",
        "Conclusions_partie_adverse.docx"
    ]
    
    selected_docs = st.multiselect(
        "Documents à comparer",
        available_docs,
        default=available_docs[:3],
        help="Sélectionnez au moins 2 documents"
    )
    
    if len(selected_docs) < 2:
        st.warning("⚠️ Sélectionnez au moins 2 documents pour détecter des contradictions")
        return
    
    # Options d'analyse
    st.markdown("### 2. Paramètres d'analyse")
    
    col1, col2 = st.columns(2)
    
    with col1:
        focus_types = st.multiselect(
            "Types de contradictions à chercher",
            ["Dates", "Montants", "Personnes", "Faits"],
            default=["Dates", "Montants", "Personnes"]
        )
    
    with col2:
        sensitivity = st.select_slider(
            "Sensibilité de détection",
            ["Faible", "Normale", "Élevée"],
            value="Normale"
        )
    
    # Bouton d'analyse
    if st.button("🔍 Lancer l'analyse", type="primary", use_container_width=True):
        analyze_contradictions(selected_docs, focus_types, sensitivity)


def analyze_contradictions(docs: List[str], focus_types: List[str], sensitivity: str):
    """Lance l'analyse de contradictions."""
    detector = ContradictionDetector()
    
    with st.spinner("Analyse en cours..."):
        # Simuler le chargement des documents
        progress = st.progress(0)
        
        # Simuler des documents avec du contenu
        documents = []
        for i, doc_name in enumerate(docs):
            progress.progress((i + 1) / len(docs))
            
            # Contenu simulé selon le type de document
            if "audition_MARTIN_15012025" in doc_name:
                content = """
                Le 15 janvier 2025, M. MARTIN déclare avoir rencontré M. DURAND
                le 10 décembre 2024 à 14h30 dans ses bureaux. Il affirme qu'un
                montant de 150 000 euros a été convenu pour la transaction.
                M. MARTIN nie avoir reçu des instructions de sa hiérarchie.
                """
            elif "audition_MARTIN_20012025" in doc_name:
                content = """
                Lors de sa seconde audition le 20 janvier 2025, M. MARTIN
                précise que la rencontre avec M. DURAND a eu lieu le 12 décembre 2024
                à 15h00. Il mentionne maintenant un montant de 145 000 euros.
                M. MARTIN reconnaît avoir consulté sa hiérarchie avant la transaction.
                """
            else:
                content = f"Contenu simulé du document {doc_name}"
            
            documents.append({
                'name': doc_name,
                'content': content,
                'metadata': {'date': datetime.now()}
            })
        
        # Mapper les types
        type_map = {
            'Dates': 'date',
            'Montants': 'amount',
            'Personnes': 'person',
            'Faits': 'fact'
        }
        mapped_types = [type_map.get(t, t.lower()) for t in focus_types]
        
        # Détecter les contradictions
        contradictions = detector.detect_contradictions(documents, mapped_types)
        
        # Générer le rapport
        report = detector.generate_contradiction_report(contradictions)
        
        # Afficher les résultats
        display_contradiction_results(contradictions, report)


def display_contradiction_results(contradictions: List[Any], report: Dict[str, Any]):
    """Affiche les résultats de l'analyse."""
    st.markdown("### 📊 Résultats de l'analyse")
    
    # Métriques générales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total", len(contradictions))
    
    with col2:
        high_severity = sum(1 for c in contradictions if c.severity == 'high')
        st.metric("Haute sévérité", high_severity, delta_color="inverse")
    
    with col3:
        st.metric("Types détectés", len(report.get('by_type', {})))
    
    with col4:
        confidence_avg = sum(c.confidence for c in contradictions) / len(contradictions) if contradictions else 0
        st.metric("Confiance moy.", f"{confidence_avg:.0%}")
    
    # Résumé
    st.info(f"💡 {report.get('summary', 'Analyse terminée')}")
    
    # Détail des contradictions
    if contradictions:
        st.markdown("### 🚨 Contradictions détectées")
        
        # Filtrer par sévérité
        severity_filter = st.radio(
            "Filtrer par sévérité",
            ["Toutes", "Haute", "Moyenne", "Faible"],
            horizontal=True
        )
        
        # Afficher chaque contradiction
        for i, contradiction in enumerate(contradictions):
            if severity_filter != "Toutes" and contradiction.severity != severity_filter.lower():
                continue
            
            # Couleur selon la sévérité
            severity_colors = {
                'high': '🔴',
                'medium': '🟡',
                'low': '🟢'
            }
            
            with st.expander(
                f"{severity_colors.get(contradiction.severity, '⚪')} "
                f"{contradiction.type.upper()} - {contradiction.explanation}"
            ):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**📄 {contradiction.document1}**")
                    st.write(contradiction.statement1)
                    st.caption(f"Contexte : {contradiction.context1[:100]}...")
                
                with col2:
                    st.markdown(f"**📄 {contradiction.document2}**")
                    st.write(contradiction.statement2)
                    st.caption(f"Contexte : {contradiction.context2[:100]}...")
                
                st.progress(contradiction.confidence)
                st.caption(f"Confiance : {contradiction.confidence:.0%}")
                
                # Actions
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("📝 Noter", key=f"note_{i}"):
                        st.info("Fonction de notes en développement")
                
                with col2:
                    if st.button("🔍 Analyser", key=f"analyze_{i}"):
                        st.info("Analyse approfondie en développement")
                
                with col3:
                    if st.button("📤 Exporter", key=f"export_{i}"):
                        st.info("Export en développement")
        
        # Bouton d'export global
        st.markdown("### 📤 Actions")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📄 Générer rapport Word", use_container_width=True):
                st.success("Rapport généré (simulation)")
        
        with col2:
            if st.button("📊 Exporter Excel", use_container_width=True):
                st.success("Export Excel (simulation)")
        
        with col3:
            if st.button("🤖 Analyser avec IA", use_container_width=True):
                if MULTI_LLM_AVAILABLE:
                    analyze_with_ai(contradictions)
                else:
                    st.error("Module Multi-LLM non disponible")
    
    else:
        st.success("✅ Aucune contradiction détectée entre les documents sélectionnés")


def analyze_with_ai(contradictions: List[Any]):
    """Analyse les contradictions avec l'IA."""
    st.markdown("### 🤖 Analyse IA des contradictions")
    
    # Préparer le contexte
    context = "Contradictions détectées :\n\n"
    for c in contradictions[:5]:  # Limiter à 5 pour le contexte
        context += f"- {c.type}: {c.explanation}\n"
        context += f"  Doc1: {c.statement1}\n"
        context += f"  Doc2: {c.statement2}\n\n"
    
    prompt = """En tant qu'avocat pénaliste expert, analysez ces contradictions et indiquez :
    1. Leur impact sur la défense
    2. Les questions à poser pour clarifier
    3. La stratégie recommandée"""
    
    # Utiliser le multi-LLM manager
    manager = MultiLLMManager()
    
    with st.spinner("Interrogation de l'IA..."):
        # Simuler une réponse
        st.info("🤖 **Analyse IA**")
        st.write("""
        **1. Impact sur la défense :**
        Les contradictions sur les dates et montants fragilisent la crédibilité 
        du témoin principal. Cela peut être exploité pour demander une confrontation.
        
        **2. Questions de clarification :**
        - Demander au témoin d'expliquer les variations de dates
        - Clarifier la source des montants mentionnés
        - Vérifier l'existence de documents corroborants
        
        **3. Stratégie recommandée :**
        Utiliser ces contradictions pour demander des actes d'instruction 
        complémentaires et remettre en cause la fiabilité des témoignages.
        """)


def render_chronology_analysis():
    """Interface pour l'analyse chronologique."""
    st.header("📅 Analyse chronologique")
    
    # Type de chronologie
    chrono_type = st.selectbox(
        "Type de chronologie",
        ["Chronologie des faits", "Chronologie procédurale", "Chronologie financière", "Chronologie complète"]
    )
    
    # Période
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Date de début")
    with col2:
        end_date = st.date_input("Date de fin")
    
    if st.button("📅 Générer la chronologie", type="primary"):
        st.info("🚧 Fonction en développement")
        
        # Exemple de chronologie
        st.markdown("### Chronologie des événements")
        
        events = [
            {"date": "10/12/2024", "type": "Rencontre", "desc": "Première rencontre MARTIN-DURAND"},
            {"date": "15/12/2024", "type": "Transaction", "desc": "Virement de 150 000€"},
            {"date": "15/01/2025", "type": "Procédure", "desc": "Première audition MARTIN"},
            {"date": "20/01/2025", "type": "Procédure", "desc": "Seconde audition MARTIN"},
        ]
        
        for event in events:
            st.write(f"**{event['date']}** - {event['type']} : {event['desc']}")


def render_relation_analysis():
    """Interface pour l'analyse relationnelle."""
    st.header("🔗 Analyse des relations")
    st.info("🚧 Module d'analyse relationnelle en développement")
    
    # Placeholder pour le graphe de relations
    st.write("Visualisation des liens entre :")
    st.write("- Personnes physiques")
    st.write("- Personnes morales")
    st.write("- Flux financiers")
    st.write("- Documents")


def render_prescription_calculator():
    """Calculateur de prescription pénale."""
    st.header("⚖️ Calculateur de prescription")
    
    col1, col2 = st.columns(2)
    
    with col1:
        date_faits = st.date_input("Date des faits")
        type_infraction = st.selectbox(
            "Type d'infraction",
            ["Crime", "Délit", "Contravention"]
        )
        recidive = st.checkbox("Récidive")
    
    with col2:
        dernier_acte = st.date_input("Dernier acte interruptif")
        
        # Délais selon le type
        delais = {
            "Crime": 20,
            "Délit": 6,
            "Contravention": 1
        }
        
        st.info(f"Délai de base : {delais[type_infraction]} ans")
    
    if st.button("Calculer la prescription", type="primary"):
        # Calcul simple
        from datetime import timedelta
        
        delai = delais[type_infraction]
        if recidive:
            delai *= 2
        
        date_prescription = dernier_acte + timedelta(days=delai*365)
        jours_restants = (date_prescription - datetime.now().date()).days
        
        if jours_restants > 0:
            st.success(f"✅ Prescription le : {date_prescription.strftime('%d/%m/%Y')}")
            st.metric("Jours restants", jours_restants)
            
            # Barre de progression
            progress = max(0, min(1, 1 - (jours_restants / (delai * 365))))
            st.progress(progress)
        else:
            st.error("❌ Prescription acquise")


def render_strategy_analysis():
    """Interface pour l'analyse stratégique."""
    st.header("💡 Analyse stratégique")
    
    strategy_type = st.selectbox(
        "Type d'analyse stratégique",
        ["Analyse SWOT", "Scénarios de défense", "Évaluation des risques", "Stratégie d'audience"]
    )
    
    if strategy_type == "Analyse SWOT":
        st.markdown("### Analyse SWOT du dossier")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### ✅ Forces")
            st.text_area("", value="- Contradictions dans les témoignages\n- Absence de preuves matérielles", height=150)
            
            st.markdown("#### 🎯 Opportunités")
            st.text_area("", value="- Jurisprudence favorable récente\n- Possibilité de nullités", height=150)
        
        with col2:
            st.markdown("#### ⚠️ Faiblesses")
            st.text_area("", value="- Documents comptables défavorables\n- Témoins à charge multiples", height=150)
            
            st.markdown("#### 🚨 Menaces")
            st.text_area("", value="- Risque de nouvelles auditions\n- Expertise défavorable possible", height=150)
    
    else:
        st.info(f"🚧 Module '{strategy_type}' en développement")


# Export
__all__ = ['render_analysis_page']
