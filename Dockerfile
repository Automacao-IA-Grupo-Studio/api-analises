# ── Imagem base: Node.js LTS + Debian Bookworm ───────────────────────────────
FROM node:20-bookworm-slim

# ── Dependências do sistema (Python, Tesseract OCR) ───────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    tesseract-ocr \
    tesseract-ocr-por \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# ── Dependências Python ───────────────────────────────────────────────────────
COPY requirements.txt /app/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /app/requirements.txt

# ── Dependências Node.js ──────────────────────────────────────────────────────
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev

# ── Código-fonte ──────────────────────────────────────────────────────────────
COPY . .
RUN mkdir -p /app/data/jobs

# ── Variáveis de ambiente padrão ──────────────────────────────────────────────
# (Banco agora é SQLite local — não precisa mais de DB_HOST/PORT/USER/PASS)
ENV PORT=3030 \
    PYTHON_BIN=python3 \
    NODE_ENV=production

EXPOSE 3030
CMD ["node", "server.js"]
