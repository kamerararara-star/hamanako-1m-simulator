FROM python:3.12-slim
WORKDIR /app
COPY . /app/backend
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn","backend.api:app","--host","0.0.0.0","--port","8000"]
