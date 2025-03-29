FROM python:3.13-slim

RUN apt-get update && apt-get install -y git libxml2-dev libxslt1-dev build-essential zlib1g-dev
RUN pip install --upgrade pip

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

ADD hoarderpod/ /app/hoarderpod
ADD feed.svg .
ADD pyproject.toml .

RUN pip install -e .

COPY cover.jpg .

CMD ["python", "hoarderpod/api.py"]
