FROM continuumio/miniconda3:latest

WORKDIR /usr/src/llm
COPY . .

RUN apt update -y && \
    apt install --upgrade python3 python3-pip git -y && \
    python3 -m pip install pip && \
    pip install -r requirements.txt --no-cache-dir --no-build-isolation

EXPOSE 50051
CMD python3 embedding_server.py