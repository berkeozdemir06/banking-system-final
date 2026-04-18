FROM python:3.11-slim
WORKDIR /app

# Copy backend requirements
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# In a modular monolith, FastAPI serves the frontend folder statically
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Set working directory to where main.py located
WORKDIR /app/backend

# Expose server port
EXPOSE 8000

CMD ["python", "main.py"]
