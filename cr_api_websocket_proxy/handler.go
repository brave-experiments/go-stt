package cr_api_websocket_proxy

import "time"

// HandlerConfig holds configuration for the WebSocket handlers
type HandlerConfig struct {
	WebsocketURL      string
	Timeout           time.Duration
	TryToFinalizeText bool
}

// Handler holds the configuration and provides methods that return http.HandlerFunc
type Handler struct {
	config *HandlerConfig
}

// NewHandler creates a new Handler with the given configuration
func NewHandler(config *HandlerConfig) *Handler {
	return &Handler{
		config: config,
	}
}
