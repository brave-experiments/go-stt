package cr_api_websocket_proxy

import (
	"sync"
)

type PairContexts struct {
	sync.Mutex
	pairContexts map[string]*PairContext
}

func (h *PairContexts) GetOrCreate(key string, createFn func(key string) *PairContext) *PairContext {
	h.Lock()
	defer h.Unlock()

	pairContext, exists := h.pairContexts[key]
	if !exists {
		pairContext = createFn(key)
		h.pairContexts[key] = pairContext

		go func() {
			<-pairContext.ctx.Done()
			h.Remove(key)
		}()
	}
	return pairContext
}

func (h *PairContexts) Remove(key string) {
	h.Lock()
	defer h.Unlock()

	delete(h.pairContexts, key)
}

var pairContexts = &PairContexts{
	pairContexts: make(map[string]*PairContext),
}
