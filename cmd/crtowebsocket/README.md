# Chromium to WebSocket

This is a simple HTTP server that listens for WebSpeech connections from a
Chromium browser, converts audio data to WAV format, streams it to a WebSocket
client, receives text data from the WebSocket client, and sends it back to the
Chromium browser.

## Usage

```bash
go run .
```

## Building

```bash
go build -o crtowebsocket .
```

## Running

```bash
./crtowebocket
```

## Building for release

```bash
go build -o crtowebsocket .
```

## Running for release

```bash
./crtowebsocket
```
