"""Interface Streamlit pour générer des lettres personnalisées."""
import streamlit as st

from core.letter_generator import generate_letter


def main() -> None:
    st.title("Assistant Codex")

    with st.form("lettre_formulaire"):
        st.subheader("\U0001F4C4 Générer une lettre")
        destinataire = st.text_input("Destinataire")
        objet = st.text_input("Objet")
        corps = st.text_area("Contenu (Markdown ou texte libre)")
        submitted = st.form_submit_button("Générer")
        if submitted:
            path = generate_letter(destinataire, objet, corps)
            st.success("Lettre générée.")
            with open(path, "rb") as f:
                st.download_button(
                    "\U0001F4E5 Télécharger la lettre", f, file_name="lettre.docx"
                )


if __name__ == "__main__":
    main()

