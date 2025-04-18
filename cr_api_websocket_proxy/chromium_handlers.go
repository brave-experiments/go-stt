package cr_api_websocket_proxy

import (
	"context"
	"encoding/binary"
	"net/http"
	"time"

	"github.com/brave-experiments/go-stt/google_streaming_api"

	"github.com/rs/zerolog/log"
)

// HandleUpstreamRequest handles the upstream request from Chromium.
func (h *Handler) HandleUpstreamRequest(
	w http.ResponseWriter,
	req *http.Request,
) {
	pairContext := pairContexts.getOrCreatePairContextForRequest(h, req)
	if pairContext == nil {
		return
	}

	defer pairContext.Close()
	defer close(pairContext.audioChan)

	log.Debug().Msgf("[%s] [UPSTREAM] Start", pairContext.pair)
	defer log.Debug().Msgf("[%s] [UPSTREAM] Done", pairContext.pair)

	dec, err := NewAudioDecoder(req)
	if err != nil {
		log.Warn().Msgf("[%s] [UPSTREAM] Failed to create audio decoder: %v", pairContext.pair, err)
		return
	}

	samples := audioSamplesBufferPool.Get()
	defer audioSamplesBufferPool.Put(samples)

	for {
		select {
		case <-pairContext.ctx.Done():
			return
		case <-req.Context().Done():
			log.Debug().Msgf("[%s] [UPSTREAM] Request context done: %v", pairContext.pair, req.Context().Err())
			return
		default:
			n, err := dec.Read(samples)
			if n > 0 {
				bytes := audioBytesBufferPool.Get()
				// Convert int16 samples to bytes
				for i, sample := range samples[:n] {
					binary.LittleEndian.PutUint16(bytes[i*2:], uint16(sample))
				}
				pairContext.audioChan <- bytes[:n*2]
			}
			if err != nil {
				log.Warn().Msgf("[%s] [UPSTREAM] Failed to read audio: %v", pairContext.pair, err)
				return
			}
		}
	}
}

// HandleDownstreamRequest handles the downstream request to Chromium.
func (h *Handler) HandleDownstreamRequest(
	w http.ResponseWriter,
	req *http.Request,
) {
	pairContext := pairContexts.getOrCreatePairContextForRequest(h, req)
	if pairContext == nil {
		return
	}

	defer pairContext.Close()

	log.Debug().Msgf("[%s] [DOWNSTREAM] Start", pairContext.pair)
	defer log.Debug().Msgf("[%s] [DOWNSTREAM] Done", pairContext.pair)

	sentFinalIndices := make(
		map[int]bool,
	)
	for {
		select {
		case <-pairContext.ctx.Done():
			return
		case <-req.Context().Done():
			log.Debug().Msgf("[%s] [DOWNSTREAM] Request context done: %v", pairContext.pair, req.Context().Err())
			return
		case segments, ok := <-pairContext.results:
			if !ok {
				return
			}
			hasMessages := false
			message := google_streaming_api.NewRecognitionMessage()
			for i, segment := range segments {
				// Skip if segment is final and we've already sent it
				if h.config.TryToFinalizeText && segment.Final && sentFinalIndices[i] {
					continue
				}

				message.Add(segment.Text, h.config.TryToFinalizeText && segment.Final)
				hasMessages = true
				// Track final segments we've sent
				if h.config.TryToFinalizeText && segment.Final {
					sentFinalIndices[i] = true
				}
			}

			// Only send if we have messages to send
			if hasMessages {
				bytes, err := message.Serialize()
				if err != nil {
					log.Warn().Msgf("[%s] [DOWNSTREAM] Failed to serialize message: %v", pairContext.pair, err)
					return
				}
				binary.Write(w, binary.BigEndian, uint32(len(bytes)))
				w.Write(bytes)
				if fl, ok := w.(http.Flusher); ok {
					fl.Flush()
				}
			}
		}
	}
}

func (hs *PairContexts) getOrCreatePairContextForRequest(
	h *Handler,
	req *http.Request,
) *PairContext {
	isUpstreamRequest := req.URL.Path == "/up"
	isDownstreamRequest := req.URL.Path == "/down"

	if !isUpstreamRequest && !isDownstreamRequest {
		return nil
	}

	err := req.ParseForm()
	if err != nil {
		log.Debug().Msgf("[UPSTREAM] Failed to parse form: %v", err)
		return nil
	}

	pair := req.FormValue("pair")
	if pair == "" {
		log.Debug().Msgf("[UPSTREAM] Pair is empty")
		return nil
	}

	pairContext := hs.GetOrCreate(
		pair,
		func(pair string) *PairContext {
			ctx, cancel := context.WithDeadline(
				context.Background(),
				time.Now().Add(h.config.Timeout),
			)
			pairContext := &PairContext{
				pair:      pair,
				audioChan: make(chan []byte, bytesPerChunk),
				results:   make(chan []TextSegment, 10),
				ctx:       ctx,
				cancel:    cancel,
			}
			return pairContext
		},
	)

	if isUpstreamRequest {
		lang := req.FormValue("lang")
		if len(lang) > 2 {
			lang = lang[:2]
		} else {
			log.Warn().Msgf("[UPSTREAM] Language is empty, using default: %s", lang)
			lang = "en"
		}
		pairContext.lang = lang
		go processAudioOverWebSocket(h, pairContext)

		pairContext.SetUpstreamConnected()
	}

	if isDownstreamRequest {
		pairContext.SetDownstreamConnected()
	}

	if pairContext.IsPaired() {
		log.Info().Msgf("[%s] PairContext is paired", pair)
		hs.Remove(pair)
	}

	return pairContext
}
