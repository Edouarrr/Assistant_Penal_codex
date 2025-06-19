# ui/pages/search_interactive.py
"""Page de recherche avec système de dialogue interactif."""
import streamlit as st
from datetime import datetime
from typing import Dict, List, Any, Optional

# Import des modules
from core.search.dialogue_manager import DialogueManager
from core.llm.multi_llm_manager import MultiLLMManager  # À créer
from core.security.rgpd_manager import RGPDManager


class InteractiveSearchPage:
    """Gère la page de recherche avec dialogue interactif."""
    
    def __init__(self):
        self.dialogue_manager = DialogueManager()
        self.multi_llm = MultiLLMManager()
        self.rgpd = RGPDManager()
        
        # Initialisation de l'état de session
        if 'search_state' not in st.session_state:
            st.session_state.search_state = 'waiting'  # waiting, clarifying, processing, complete
        if 'current_query' not in st.session_state:
            st.session_state.current_query = ""
        if 'clarification_questions' not in st.session_state:
            st.session_state.clarification_questions = []
        if 'user_responses' not in st.session_state:
            st.session_state.user_responses = {}
        if 'search_results' not in st.session_state:
            st.session_state.search_results = None
        if 'question_round' not in st.session_state:
            st.session_state.question_round = 0
    
    def render(self, username: str):
        """Affiche la page de recherche interactive."""
        st.title("🔍 Assistant de recherche intelligent")
        
        # Afficher l'état actuel
        self._display_status()
        
        # Zone de requête principale
        self._render_search_input()
        
        # Zone de dialogue si en mode clarification
        if st.session_state.search_state == 'clarifying':
            self._render_clarification_dialogue()
        
        # Affichage des résultats si disponibles
        if st.session_state.search_state == 'complete' and st.session_state.search_results:
            self._render_results()
        
        # Historique de conversation dans la sidebar
        with st.sidebar:
            self._render_conversation_history()
    
    def _display_status(self):
        """Affiche l'état actuel du processus."""
        status_messages = {
            'waiting': "💭 En attente de votre requête...",
            'clarifying': "🤔 J'ai besoin de quelques précisions pour mieux vous aider",
            'processing': "⚡ Traitement en cours avec les IA sélectionnées...",
            'complete': "✅ Recherche terminée"
        }
        
        if st.session_state.search_state in status_messages:
            if st.session_state.search_state == 'clarifying':
                st.info(status_messages[st.session_state.search_state])
            elif st.session_state.search_state == 'processing':
                st.warning(status_messages[st.session_state.search_state])
            elif st.session_state.search_state == 'complete':
                st.success(status_messages[st.session_state.search_state])
    
    def _render_search_input(self):
        """Affiche la barre de recherche principale."""
        # Container pour la recherche
        with st.container():
            col1, col2 = st.columns([5, 1])
            
            with col1:
                # Zone de texte pour la requête
                query = st.text_area(
                    "Votre requête",
                    value=st.session_state.current_query,
                    height=100,
                    placeholder=(
                        "Décrivez ce que vous cherchez ou ce que vous voulez faire...\n"
                        "Exemples :\n"
                        "- @dossier_martin analyse les contradictions dans les auditions\n"
                        "- Rédige une plainte pour escroquerie\n"
                        "- Trouve la jurisprudence sur le blanchiment aggravé"
                    ),
                    key="main_query_input",
                    disabled=st.session_state.search_state in ['clarifying', 'processing']
                )
            
            with col2:
                st.write("")  # Espaceur pour alignement
                # Bouton d'exécution immédiate
                force_execute = st.button(
                    "⚡ Exécuter\nsans questions",
                    key="force_execute",
                    help="Lance la recherche immédiatement sans poser de questions",
                    disabled=st.session_state.search_state == 'processing'
                )
            
            # Options de recherche
            with st.expander("⚙️ Options avancées", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    # Sélection des modèles IA
                    selected_models = st.multiselect(
                        "🤖 Modèles IA à utiliser",
                        options=["GPT-4o", "Claude Opus 4", "Perplexity", "Mistral", "Gemini", "DeepSeek"],
                        default=["GPT-4o", "Claude Opus 4"],
                        key="selected_models"
                    )
                    
                    # Sources de recherche
                    search_sources = st.multiselect(
                        "📚 Sources de recherche",
                        options=["Documents vectorisés", "Legifrance", "Judilibre", "Internet"],
                        default=["Documents vectorisés"],
                        key="search_sources"
                    )
                
                with col2:
                    # Mode de fusion
                    fusion_mode = st.select_slider(
                        "🔄 Mode de fusion des réponses",
                        options=["Comparatif", "Synthétique", "Contradictoire", "Exhaustif", "Consensuel"],
                        value="Synthétique",
                        key="fusion_mode"
                    )
                    
                    # Estimation des coûts
                    estimate_cost = st.checkbox(
                        "💰 Estimer le coût avant exécution",
                        value=True,
                        key="estimate_cost"
                    )
            
            # Boutons d'action
            col1, col2, col3 = st.columns([2, 2, 2])
            
            with col1:
                if st.button(
                    "🔍 Analyser ma requête",
                    type="primary",
                    disabled=st.session_state.search_state != 'waiting' or not query,
                    use_container_width=True
                ):
                    self._start_analysis(query, username)
            
            with col2:
                if st.button(
                    "🔄 Nouvelle recherche",
                    disabled=st.session_state.search_state == 'processing',
                    use_container_width=True
                ):
                    self._reset_search()
            
            with col3:
                if st.button(
                    "📋 Voir l'historique",
                    use_container_width=True
                ):
                    st.session_state.show_history = not st.session_state.get('show_history', False)
            
            # Forcer l'exécution si demandé
            if force_execute and query:
                self._execute_search(query, username, skip_clarification=True)
    
    def _start_analysis(self, query: str, username: str):
        """Démarre l'analyse de la requête."""
        st.session_state.current_query = query
        st.session_state.search_state = 'clarifying'
        
        # Analyser la requête
        analysis = self.dialogue_manager.analyze_query(query)
        
        # Si haute confiance ou pas besoin de clarification
        if analysis['confidence'] > 0.8 or not analysis['needs_clarification']:
            self._execute_search(query, username, skip_clarification=True)
        else:
            # Préparer les questions
            st.session_state.clarification_questions = analysis['questions']
            st.session_state.question_round = 1
            st.rerun()
    
    def _render_clarification_dialogue(self):
        """Affiche le dialogue de clarification."""
        st.markdown("### 💬 Dialogue de précision")
        
        # Afficher le round de questions
        st.caption(f"Round {st.session_state.question_round} de questions")
        
        # Container pour les questions
        with st.form("clarification_form"):
            responses = {}
            
            # Afficher chaque question
            for i, question in enumerate(st.session_state.clarification_questions):
                st.markdown(f"**{i+1}. {question['text']}**")
                
                if question['type'] == 'choice':
                    responses[question['id']] = st.selectbox(
                        "",
                        options=[""] + question['options'],
                        key=f"q_{question['id']}",
                        label_visibility="collapsed"
                    )
                
                elif question['type'] == 'text':
                    responses[question['id']] = st.text_input(
                        "",
                        key=f"q_{question['id']}",
                        placeholder="Votre réponse...",
                        label_visibility="collapsed"
                    )
                
                elif question['type'] == 'date':
                    responses[question['id']] = st.date_input(
                        "",
                        key=f"q_{question['id']}",
                        label_visibility="collapsed"
                    )
                
                elif question['type'] == 'multiselect':
                    responses[question['id']] = st.multiselect(
                        "",
                        options=question['options'],
                        key=f"q_{question['id']}",
                        label_visibility="collapsed"
                    )
                
                st.write("")  # Espacement
            
            # Boutons d'action
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                submit = st.form_submit_button(
                    "✅ Répondre",
                    type="primary",
                    use_container_width=True
                )
            
            with col2:
                more_questions = st.form_submit_button(
                    "➕ Plus de questions",
                    use_container_width=True
                )
            
            with col3:
                execute_now = st.form_submit_button(
                    "⚡ Exécuter maintenant",
                    use_container_width=True
                )
            
            with col4:
                cancel = st.form_submit_button(
                    "❌ Annuler",
                    use_container_width=True
                )
        
        # Traiter les actions
        if submit:
            # Sauvegarder les réponses
            st.session_state.user_responses.update(responses)
            
            # Vérifier si on a besoin de plus de questions
            if self.dialogue_manager.should_ask_more_questions(st.session_state.user_responses):
                # Générer des questions de suivi
                followup = self.dialogue_manager.generate_followup_questions(
                    st.session_state.current_query,
                    st.session_state.user_responses
                )
                st.session_state.clarification_questions = followup
                st.session_state.question_round += 1
                st.rerun()
            else:
                # Prêt à exécuter
                self._execute_search(
                    st.session_state.current_query,
                    st.session_state.get('username', 'unknown')
                )
        
        elif more_questions:
            # Générer plus de questions
            st.session_state.user_responses.update(responses)
            followup = self.dialogue_manager.generate_followup_questions(
                st.session_state.current_query,
                st.session_state.user_responses
            )
            st.session_state.clarification_questions.extend(followup)
            st.session_state.question_round += 1
            st.rerun()
        
        elif execute_now:
            # Exécuter avec les réponses actuelles
            st.session_state.user_responses.update(responses)
            self._execute_search(
                st.session_state.current_query,
                st.session_state.get('username', 'unknown')
            )
        
        elif cancel:
            self._reset_search()
    
    def _execute_search(self, query: str, username: str, skip_clarification: bool = False):
        """Exécute la recherche avec tous les paramètres."""
        st.session_state.search_state = 'processing'
        
        # Logger l'action
        self.rgpd.log_access(
            username,
            "search_execution",
            details={
                "query": query[:200],
                "models": st.session_state.get('selected_models', []),
                "clarifications": st.session_state.user_responses
            }
        )
        
        # Estimation du coût si demandé
        if st.session_state.get('estimate_cost', True):
            cost_estimate = self._estimate_query_cost(query)
            st.info(f"💰 Coût estimé : {cost_estimate:.2f} € (environ {cost_estimate * 33333:.0f} tokens)")
        
        # Simuler le traitement (à remplacer par l'appel réel)
        with st.spinner("Traitement en cours..."):
            # Progress bar
            progress = st.progress(0)
            
            # Simuler l'interrogation de chaque modèle
            models = st.session_state.get('selected_models', ['GPT-4o'])
            for i, model in enumerate(models):
                progress.progress((i + 1) / len(models))
                st.write(f"🤖 Interrogation de {model}...")
            
            # Simuler la fusion
            st.write("🔄 Fusion des réponses...")
            
            # Résultats simulés
            results = {
                'query': query,
                'models_used': models,
                'fusion_mode': st.session_state.get('fusion_mode', 'Synthétique'),
                'clarifications': st.session_state.user_responses,
                'responses': self._generate_mock_responses(models),
                'sources': self._generate_mock_sources(),
                'timestamp': datetime.now(),
                'cost': cost_estimate if st.session_state.get('estimate_cost') else None
            }
            
            st.session_state.search_results = results
            st.session_state.search_state = 'complete'
            st.rerun()
    
    def _render_results(self):
        """Affiche les résultats de la recherche."""
        results = st.session_state.search_results
        
        st.markdown("### 📊 Résultats de la recherche")
        
        # Métadonnées de la recherche
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Modèles utilisés", len(results['models_used']))
        with col2:
            st.metric("Sources consultées", len(results['sources']))
        with col3:
            if results.get('cost'):
                st.metric("Coût", f"{results['cost']:.2f} €")
        
        # Onglets pour les résultats
        tabs = st.tabs(results['models_used'] + [f"🔀 Fusion {results['fusion_mode']}"])
        
        # Réponses individuelles
        for i, (tab, model) in enumerate(zip(tabs[:-1], results['models_used'])):
            with tab:
                response = results['responses'][model]
                
                # En-tête du modèle
                st.markdown(f"#### Réponse de {model}")
                
                # Contenu de la réponse
                st.markdown(response['content'])
                
                # Sources utilisées
                if response.get('sources'):
                    st.markdown("**Sources citées :**")
                    for source in response['sources']:
                        st.write(f"- 📄 {source['document']} (page {source['page']})")
                
                # Métriques
                col1, col2 = st.columns(2)
                with col1:
                    st.caption(f"⏱️ Temps: {response['time']:.1f}s")
                with col2:
                    st.caption(f"🔤 Tokens: {response['tokens']:,}")
        
        # Onglet fusion
        with tabs[-1]:
            st.markdown(f"#### Fusion {results['fusion_mode'].lower()} des réponses")
            
            # Afficher la fusion selon le mode
            if results['fusion_mode'] == 'Synthétique':
                st.info("🔀 **Synthèse unifiée des réponses**")
                st.markdown(self._generate_synthetic_fusion(results['responses']))
            
            elif results['fusion_mode'] == 'Comparatif':
                st.info("📊 **Analyse comparative des réponses**")
                self._render_comparative_analysis(results['responses'])
            
            elif results['fusion_mode'] == 'Contradictoire':
                st.warning("⚠️ **Points de contradiction détectés**")
                self._render_contradictions(results['responses'])
            
            # Actions sur les résultats
            st.markdown("### 🎯 Actions")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📄 Générer un rapport", use_container_width=True):
                    st.info("Génération du rapport en cours...")
            
            with col2:
                if st.button("💾 Sauvegarder les résultats", use_container_width=True):
                    st.success("Résultats sauvegardés!")
            
            with col3:
                if st.button("🔄 Affiner la recherche", use_container_width=True):
                    st.session_state.search_state = 'clarifying'
                    st.rerun()
    
    def _render_conversation_history(self):
        """Affiche l'historique de conversation dans la sidebar."""
        if st.session_state.get('show_history', False):
            st.markdown("### 📜 Historique")
            
            # Historique simulé
            history = [
                {"time": "10:45", "query": "Analyse contradictions dossier Martin"},
                {"time": "09:30", "query": "Rédige conclusions nullité PV"},
                {"time": "Hier", "query": "Jurisprudence blanchiment aggravé"},
            ]
            
            for item in history:
                with st.expander(f"🕐 {item['time']}"):
                    st.write(item['query'])
                    if st.button("Relancer", key=f"rerun_{item['time']}"):
                        st.session_state.current_query = item['query']
                        self._reset_search()
                        st.rerun()
    
    def _reset_search(self):
        """Réinitialise l'état de la recherche."""
        st.session_state.search_state = 'waiting'
        st.session_state.clarification_questions = []
        st.session_state.user_responses = {}
        st.session_state.search_results = None
        st.session_state.question_round = 0
    
    def _estimate_query_cost(self, query: str) -> float:
        """Estime le coût d'une requête."""
        # Estimation basique (à remplacer par un vrai calcul)
        base_cost = 0.01  # par modèle
        models_count = len(st.session_state.get('selected_models', ['GPT-4o']))
        query_length_factor = len(query) / 100
        
        return base_cost * models_count * (1 + query_length_factor)
    
    def _generate_mock_responses(self, models: List[str]) -> Dict[str, Any]:
        """Génère des réponses simulées pour la démo."""
        responses = {}
        for model in models:
            responses[model] = {
                'content': f"Réponse simulée de {model} concernant la requête...",
                'sources': [
                    {'document': 'PV_audition_001.pdf', 'page': 12},
                    {'document': 'Conclusions_adverses.docx', 'page': 5}
                ],
                'time': 2.3,
                'tokens': 1250,
                'confidence': 0.85
            }
        return responses
    
    def _generate_mock_sources(self) -> List[Dict[str, Any]]:
        """Génère des sources simulées."""
        return [
            {'type': 'document', 'name': 'PV_audition_001.pdf', 'relevance': 0.9},
            {'type': 'jurisprudence', 'name': 'Cass. Crim. 2023', 'relevance': 0.8},
            {'type': 'article', 'name': 'Art. 432-11 CP', 'relevance': 0.95}
        ]
    
    def _generate_synthetic_fusion(self, responses: Dict[str, Any]) -> str:
        """Génère une fusion synthétique des réponses."""
        return """
        D'après l'analyse croisée des différents modèles d'IA, voici la synthèse :
        
        **Points de consensus :**
        - Tous les modèles s'accordent sur l'existence d'une contradiction majeure dans les déclarations
        - La chronologie des faits présente des incohérences notables
        
        **Éléments complémentaires :**
        - GPT-4o souligne particulièrement l'aspect procédural
        - Claude met en avant les implications juridiques
        
        **Recommandations unanimes :**
        1. Approfondir l'analyse des pièces 12 à 15
        2. Vérifier la validité des procès-verbaux
        3. Préparer une argumentation sur la nullité potentielle
        """
    
    def _render_comparative_analysis(self, responses: Dict[str, Any]):
        """Affiche une analyse comparative des réponses."""
        # Tableau comparatif
        comparison_data = []
        for model, response in responses.items():
            comparison_data.append({
                'Modèle': model,
                'Confiance': f"{response.get('confidence', 0.8)*100:.0f}%",
                'Tokens': response['tokens'],
                'Sources': len(response.get('sources', []))
            })
        
        st.dataframe(comparison_data, use_container_width=True)
    
    def _render_contradictions(self, responses: Dict[str, Any]):
        """Affiche les contradictions détectées."""
        st.write("**Contradictions identifiées :**")
        
        contradictions = [
            {
                'point': "Date de la transaction",
                'model1': "GPT-4o : 15 mars 2024",
                'model2': "Claude : 18 mars 2024",
                'severity': "high"
            },
            {
                'point': "Montant concerné",
                'model1': "Perplexity : 150,000 €",
                'model2': "Mistral : 145,000 €",
                'severity': "low"
            }
        ]
        
        for contradiction in contradictions:
            severity_color = "🔴" if contradiction['severity'] == 'high' else "🟡"
            st.write(f"{severity_color} **{contradiction['point']}**")
            st.write(f"  - {contradiction['model1']}")
            st.write(f"  - {contradiction['model2']}")


# Fonction pour intégrer dans l'app principale
def render_interactive_search_page(username: str):
    """Point d'entrée pour la page de recherche interactive."""
    page = InteractiveSearchPage()
    page.render(username)
