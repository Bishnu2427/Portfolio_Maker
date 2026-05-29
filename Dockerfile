FROM python:3.12-slim

WORKDIR /app

# System deps: gcc for C extensions, poppler for pdfplumber
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpoppler-cpp-dev \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create runtime directories
RUN mkdir -p uploads generated_portfolios

EXPOSE 5000

CMD ["python", "run.py"]
