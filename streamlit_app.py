"""Streamlit interface for Assistant Penal Codex."""
from pathlib import Path
import streamlit as st
from ui.components.header import render_header
from ui import styles
from core.letter_generator import generate_letter


def main() -> None:
    """Run the Streamlit application."""
    st.set_page_config(page_title="Assistant Penal Codex", layout="wide")
    st.markdown(styles.INTER_FONTS_CSS, unsafe_allow_html=True)
    render_header()
    
    # Initialisation de l'état de session
    if "submitted_text" not in st.session_state:
        st.session_state["submitted_text"] = ""
    
    def submit_text() -> None:
        """Callback pour soumettre le texte."""
        st.session_state["submitted_text"] = st.session_state.get("user_text", "")
        st.toast("AI response ready", icon="✅")
    
    # Formulaire d'entrée principal
    with st.form("input_form", clear_on_submit=False):
        user_text = st.text_area("Votre question", key="user_text", height=100)
        st.form_submit_button("Envoyer", on_click=submit_text)
    
    # Script JavaScript pour les raccourcis clavier
    st.components.v1.html(
        """
        <script>
        const txtArea = window.parent.document.querySelector('textarea[data-testid="stTextArea"]');
        if (txtArea) {
          txtArea.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              window.parent.document.querySelector('button[kind="primary"]').click();
            }
            if (e.key === 'Escape') {
              e.preventDefault();
              txtArea.value = '';
              txtArea.dispatchEvent(new Event('input', {bubbles: true}));
            }
            if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              alert('Command palette opened');
            }
          });
        }
        </script>
        """,
        height=0,
    )
    
    # Définition des onglets
    TABS = [
        "Chronologie",
        "Contradictions",
        "Fiches de synthèse",
        "IA",
        "Rédaction",
        "Préparation client",
        "Mindmap",
        "Dashboard",
        "Checklist audience",
        "Lettre",
        "Logs",
    ]
    
    # Création des onglets
    pages = st.tabs(TABS)
    
    # Contenu de chaque onglet
    for name, tab in zip(TABS, pages):
        with tab:
            st.write(f"Contenu de l'onglet {name}")
    
    # Command palette si disponible
    if hasattr(st, "command_palette"):
        st.command_palette({"placeholder": lambda: None})
    
    # Formulaire de génération de lettre
    with st.form("lettre_formulaire"):
        st.subheader("📄 Générer une lettre")
        destinataire = st.text_input("Destinataire")
        objet = st.text_input("Objet")
        corps = st.text_area("Contenu (Markdown ou texte libre)")
        submitted = st.form_submit_button("Générer")
        
        if submitted:
            path = generate_letter(destinataire, objet, corps)
            st.success("Lettre générée.")
            with open(path, "rb") as f:
                st.download_button("📥 Télécharger la lettre", f, file_name="lettre.docx")
    
    # Affichage du PDF dans la sidebar si disponible
    pdf_file = Path("sample.pdf")
    if pdf_file.exists():
        pdf_html = f'<iframe src="{pdf_file.as_posix()}#page=1" width="350" height="600"></iframe>'
        st.sidebar.components.v1.html(pdf_html, height=600)
    
    # Message de notification
    st.toast("Vectorization complete", icon="🎉")


if __name__ == "__main__":  # pragma: no cover - manual run
    main()