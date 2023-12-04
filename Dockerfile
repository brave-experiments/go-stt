FROM ubuntu:22.04

RUN apt update && DEBIAN_FRONTEND=noninteractive apt install -y \
        bash git make vim wget g++

ENV GOLANG_VERSION 1.20
RUN wget -nv -O - https://storage.googleapis.com/golang/go${GOLANG_VERSION}.linux-amd64.tar.gz \
    | tar -C /usr/local -xz
ENV PATH /usr/local/go/bin:$PATH

WORKDIR /app

LABEL org.opencontainers.image.description="Speech-to-Text."
LABEL org.opencontainers.image.licenses=MIT

COPY . .

WORKDIR /app
RUN make build && mv bin/transcriber /bin/ && rm -rf bin

ENTRYPOINT [ "/bin/transcriber" ]
