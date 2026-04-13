FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV INSTANCE_CONNECTION_NAME=duet-workshop-415205:us-central1:testing
ENV INSTANCE_UNIX_SOCKET=/cloudsql/duet-workshop-415205:us-central1:testing
ENV GOOGLE_GENAI_USE_VERTEXAI=True
ENV GOOGLE_CLOUD_LOCATION=global

CMD ["python", "main.py"]


