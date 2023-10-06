FROM golang:1.20-alpine3.18 as SOURCE

WORKDIR /app

RUN apk update && apk add --no-cache make git gcc g++ && \
  rm -rf /var/cache/apk/*

COPY . .

RUN make dependency && make build && \
  mv bin/transcriber /bin/ && \
  rm -rf bin && \
  apk del make git gcc g++

FROM jrottenberg/ffmpeg:6.0-alpine313

LABEL org.opencontainers.image.description="Speech-to-Text."
LABEL org.opencontainers.image.licenses=MIT

RUN apk update && apk add --no-cache curl && \
  rm -rf /var/cache/apk/*

WORKDIR /app

COPY --from=SOURCE /bin/transcriber /bin/transcriber

ENTRYPOINT [ "/bin/transcriber" ]