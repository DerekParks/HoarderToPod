FROM python:3.13-slim

RUN apt-get update && apt-get install -y git libxml2-dev libxslt1-dev build-essential zlib1g-dev
RUN pip install --upgrade pip

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY run.py .
COPY api.py .
COPY cover.jpg .

CMD ["python", "hoarderpod/api.py"]