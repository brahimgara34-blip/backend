FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev git && rm -rf /var/lib/apt/lists/*

# Copy local files if present in context
COPY . .

# If requirements.txt is missing in context (e.g. standalone Dockerfile build context in Easypanel), clone repository
RUN if [ ! -f requirements.txt ]; then \
      git clone https://github.com/brahimgara34-blip/backend.git /tmp/repo && \
      cp -r /tmp/repo/. /app/ && \
      rm -rf /tmp/repo; \
    fi

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
