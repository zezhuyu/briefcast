FROM postgres:17.4

RUN apt-get update && apt-get install -y postgresql-server-dev-17 make gcc git \
 && git clone --depth 1 https://github.com/pgvector/pgvector.git \
 && cd pgvector && make && make install \
 && rm -rf /var/lib/apt/lists/*