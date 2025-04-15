package cr_api_websocket_proxy

import (
	"context"
	"strings"
	"sync"
	"time"

	"github.com/rs/zerolog/log"
)

const textPartFinalizeDelay = 5 * time.Second // Time to wait before marking text as final

type TextSegment struct {
	Text      string
	Timestamp time.Time
	Final     bool
}

type PairContext struct {
	sync.Mutex
	pair                string
	lang                string
	audioChan           chan []byte
	results             chan []TextSegment
	ctx                 context.Context
	cancel              context.CancelFunc
	upstreamConnected   bool
	downstreamConnected bool
	textCache           []TextSegment
}

func (h *PairContext) SetUpstreamConnected() {
	h.Lock()
	h.upstreamConnected = true
	h.Unlock()
}

func (h *PairContext) SetDownstreamConnected() {
	h.Lock()
	h.downstreamConnected = true
	h.Unlock()
}

func (h *PairContext) IsPaired() bool {
	h.Lock()
	defer h.Unlock()
	return h.upstreamConnected && h.downstreamConnected
}

func (h *PairContext) Close() {
	log.Debug().Msgf("[%s] Closing pairContext", h.pair)
	h.cancel() // Signal all goroutines to stop
}

func (h *PairContext) updateTextCache(newText string) {
	h.Lock()
	defer h.Unlock()

	// Split text into parts
	parts := strings.Split(newText, " ")

	currentTime := time.Now()
	newCache := make([]TextSegment, len(parts))

	// Process each part
	for i, part := range parts {
		if i < len(parts)-1 {
			part += " "
		}

		// Check if part exists in cache
		found := false
		for _, cached := range h.textCache {
			if cached.Text == part {
				// Keep existing cache entry
				newCache[i] = cached
				found = true
				break
			}
		}

		if !found {
			// Add new part
			newCache[i] = TextSegment{
				Text:      part,
				Timestamp: currentTime,
				Final:     false,
			}
		}
	}

	// Mark parts as final if they haven't changed for textPartFinalizeDelay
	for i := range newCache {
		if !newCache[i].Final && currentTime.Sub(newCache[i].Timestamp) > textPartFinalizeDelay {
			newCache[i].Final = true
		}
	}

	h.textCache = newCache
	h.results <- newCache
}
