import importlib

REQUIRED_MODULES = [
    'streamlit', 'flask', 'openai', 'anthropic', 'mistralai', 'tiktoken',
    'PyMuPDF', 'docx', 'pypdf', 'pdf2image', 'pandas', 'numpy',
    'easyocr', 'pytesseract', 'PIL', 'networkx', 'matplotlib', 'plotly',
    'msal', 'requests', 'googleapiclient', 'google.auth', 'google.cloud.vision',
    'chromadb', 'langchain', 'dotenv', 'yaml', 'tqdm'
]

print("🔍 Vérification des modules requis...\n")

for module in REQUIRED_MODULES:
    try:
        importlib.import_module(module)
        print(f"✅ {module}")
    except ImportError:
        print(f"❌ {module} manquant")

print("\n✔️ Terminé.")

