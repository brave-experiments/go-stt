package cr_api_websocket_proxy

import (
	"bytes"
	"net/http"
	"net/url"
	"time"
	"unicode/utf8"

	"github.com/gorilla/websocket"
	"github.com/rs/zerolog/log"
)

func processAudioOverWebSocket(h *Handler, pairContext *PairContext) {
	defer pairContext.Close()
	defer close(pairContext.results)

	// parse wsURL
	u, err := url.Parse(h.config.WebsocketURL)
	if err != nil {
		log.Error().
			Err(err).
			Msg("Failed to parse WebSocket URL")
		return
	}

	// set parameters
	q := u.Query()
	q.Set("output_native", "True")
	q.Set("not_use_prompt", "False")
	q.Set("denoise", "False")
	q.Set("lang", pairContext.lang)
	u.RawQuery = q.Encode()
	wsURL := u.String()

	wsDialer := websocket.Dialer{HandshakeTimeout: 10 * time.Second}
	headers := http.Header{}

	log.Debug().Msgf("[%s] Dialing %s", pairContext.pair, wsURL)
	wsConn, _, err := wsDialer.Dial(wsURL, headers)
	if wsConn == nil || err != nil {
		log.Error().Err(err).Msg("Failed to connect to WebSocket")
		return
	}
	log.Debug().Msgf("[%s] Connected to %s", pairContext.pair, wsURL)

	defer func() {
		if wsConn == nil {
			return
		}
		log.Debug().Msgf("[%s] Closing WebSocket connection", pairContext.pair)
		wsConn.WriteControl(
			websocket.CloseMessage,
			websocket.FormatCloseMessage(websocket.CloseNormalClosure, ""),
			time.Now().Add(time.Second),
		)
		for {
			if _, _, err := wsConn.NextReader(); err != nil {
				break
			}
		}
	}()

	// Configure WebSocket connection
	wsConn.SetReadLimit(32768) // 32KB max message size
	wsConn.SetWriteDeadline(time.Now().Add(60 * time.Second))
	wsConn.SetReadDeadline(time.Now().Add(60 * time.Second))
	wsConn.SetPongHandler(
		func(string) error {
			if wsConn != nil {
				wsConn.SetReadDeadline(time.Now().Add(60 * time.Second))
			}
			return nil
		},
	)

	// Handle the WebSocket disconnect
	wsConn.SetCloseHandler(
		func(code int, text string) error {
			log.Debug().Msgf("[%s] WebSocket disconnected with code %d: %s", pairContext.pair, code, text)
			pairContext.Close()
			return nil
		},
	)

	// Handle incoming text messages
	go func() {
		for {
			select {
			case <-pairContext.ctx.Done():
				return
			default:
				messageType, message, err := wsConn.ReadMessage()
				if err != nil {
					if websocket.IsCloseError(
						err,
						websocket.CloseNormalClosure,
						websocket.CloseGoingAway,
					) {
						log.Debug().Msg("WebSocket closed normally")
					} else {
						log.Error().Err(err).Msg("WebSocket read error")
					}
					return
				}

				log.Debug().Msgf("Read message type: %d", messageType)

				var text string
				switch messageType {
				case websocket.TextMessage:
					text = string(message)
				case websocket.BinaryMessage:
					text = string(bytes.TrimRight(message, "\x00")) // Try to convert binary to UTF-8 string
					if !utf8.ValidString(text) {
						log.Warn().Msg("Received invalid UTF-8 in binary message")
						continue
					}
				default:
					log.Error().Msgf("Received unsupported message type: %d", messageType)
					continue
				}

				log.Debug().Msgf("Received text: %s", text)
				pairContext.updateTextCache(text)
			}
		}
	}()

	defer pairContext.Close()

	// Initialize WAV file writer for in enabled builds
	var wavWriter *wavFileWriter
	initWavWriter(&wavWriter, pairContext.pair)
	defer closeWavWriter(wavWriter)

	for {
		select {
		case <-pairContext.ctx.Done():
			log.Debug().Msgf("[%s] PairContext cancelled", pairContext.pair)
			return
		case audioBytes, ok := <-pairContext.audioChan:
			if !ok {
				log.Debug().Msgf("[%s] Audio channel closed", pairContext.pair)
				return
			}

			// Write audio data to WAV file in debug builds
			writeToWavFile(wavWriter, audioBytes)

			if wsConn == nil {
				log.Error().Msg("WebSocket connection is nil")
				return
			}

			err := wsConn.WriteMessage(websocket.BinaryMessage, audioBytes)
			audioBytesBufferPool.Put(audioBytes)
			if err != nil {
				log.Error().Err(err).Msg("Failed to send audio")
				return
			}
		}
	}
}
