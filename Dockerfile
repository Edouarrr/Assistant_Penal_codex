# Multi-stage build pour optimiser le cache et réduire le temps de build
FROM python:3.12-slim as builder

# Variables d'environnement pour optimiser pip
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    PYTHONUNBUFFERED=1

# Installer les dépendances système nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Créer un environnement virtuel
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copier uniquement requirements.txt d'abord (pour le cache)
WORKDIR /app
COPY requirements.txt .

# Installer les dépendances en plusieurs étapes pour éviter les timeouts
# Étape 1: Dépendances légères
RUN pip install --no-cache-dir \
    streamlit==1.40.2 \
    python-dotenv==1.0.1 \
    pandas==2.2.3 \
    numpy==1.26.4 \
    msal==1.31.1 \
    python-docx==1.1.2 \
    PyPDF2==3.0.1

# Étape 2: Dépendances moyennes
RUN pip install --no-cache-dir \
    openai==1.58.1 \
    anthropic==0.40.0 \
    chromadb==0.5.23 \
    langchain==0.3.13

# Étape 3: Dépendances lourdes (Google Cloud)
RUN pip install --no-cache-dir \
    google-cloud-vision==3.8.1 \
    google-api-python-client==2.155.0

# Étape 4: Reste des dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Stage final - image de production
FROM python:3.12-slim

# Installer uniquement les runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copier l'environnement virtuel du builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Créer le répertoire de travail
WORKDIR /app

# Créer les répertoires nécessaires
RUN mkdir -p /app/data/vector_db \
    /app/data/ocr_output \
    /app/data/logs \
    /app/data/temp \
    /app/data/pieces_communiquees

# Copier le code de l'application
COPY . .

# Port Streamlit
EXPOSE 8501

# Commande de démarrage
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]