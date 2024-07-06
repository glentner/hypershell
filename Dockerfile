FROM python:3.12-slim

LABEL version="2.5.2"
LABEL authors="glentner@purdue.edu"


RUN apt-get update && \
    apt-get upgrade --yes && \
    rm -rf /var/lib/apt/lists/*

RUN addgroup --gid 1001 --system app && \
    adduser --no-create-home --shell /bin/false --disabled-password --uid 1001 --system --group app

WORKDIR /app
COPY . .
RUN pip install poetry psycopg2 && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev

ENV HYPERSHELL_LOGGING_LEVEL=DEBUG \
    HYPERSHELL_LOGGING_STYLE=SYSTEM

USER app
ENTRYPOINT ["hs", "server"]
CMD ["--forever"]
