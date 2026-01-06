FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for uploads and data
RUN mkdir -p uploads user_resumes user_transcripts generated_cover_letters instance

# Expose port 7860 (HF Spaces default)
EXPOSE 7860

# Run the application
CMD ["python", "app.py"]
