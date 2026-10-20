# Dockerfile for Kristiansand Kommune - Helse og Mestring AI Økonomirådgiver MVP
FROM python:3.12-slim

# Sett arbeidskatalog
WORKDIR /app

# Installer systemavhengigheter for SQLite, PDF-behandling og byggverktøy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Kopier kravliste og installer Python-pakker
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Kopier prosjektfiler
COPY . .

# Opprett nødvendige datamapper dersom de mangler
RUN mkdir -p data/db data/knowledge_base notebooks assets reports

# Bygg/initialiser SQLite-databasen under container-oppstart dersom den ikke finnes
RUN python app/build_rag_index.py

# Eksponer Streamlit sin standardport
EXPOSE 8501

# Helsekontroll for Streamlit
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Start Streamlit-applikasjonen
CMD ["python", "-m", "streamlit", "run", "app/frontend.py", "--server.port=8501", "--server.address=0.0.0.0"]
