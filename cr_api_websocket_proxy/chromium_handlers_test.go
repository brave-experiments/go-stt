package cr_api_websocket_proxy

import (
	"context"
	"encoding/binary"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/brave-experiments/go-stt/google_streaming_api"
	"github.com/gorilla/websocket"
	"google.golang.org/protobuf/proto"
)

// Add this type at the top level
type infiniteReader struct {
	audio    []byte
	done     chan struct{}
	position int
}

func newInfiniteReader(audio []byte) *infiniteReader {
	return &infiniteReader{
		audio:    audio,
		done:     make(chan struct{}),
		position: 0,
	}
}

func (r *infiniteReader) Read(p []byte) (n int, err error) {
	select {
	case <-r.done:
		return 0, io.EOF
	default:
		if r.position >= len(r.audio) {
			return 0, nil
		}

		// Copy remaining audio data
		n = copy(p, r.audio[r.position:])
		r.position += n
		// Add small delay between iterations
		time.Sleep(10 * time.Millisecond)
		return n, nil
	}
}

func (r *infiniteReader) Close() {
	close(r.done)
}

// Add at the top level
type responseRecorder struct {
	io.Writer
	done chan struct{}
	http.Flusher
}

func (r *responseRecorder) Header() http.Header {
	return make(http.Header)
}

func (r *responseRecorder) Write(b []byte) (int, error) {
	return r.Writer.Write(b)
}

func (r *responseRecorder) WriteHeader(statusCode int) {}

func (r *responseRecorder) Flush() {}

func (r *responseRecorder) CloseNotify() <-chan bool {
	notify := make(chan bool, 1)
	go func() {
		<-r.done
		notify <- true
	}()
	return notify
}

// Test Helpers and Mocks
// ----------------------------------------

// Test WebSocket Server Setup
// ----------------------------------------

func setupTestWebSocketServer(t *testing.T) *httptest.Server {
	wsServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		upgrader := websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool { return true },
		}
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			t.Errorf("Failed to upgrade connection: %v", err)
			return
		}
		defer conn.Close()

		for {
			messageType, _, err := conn.ReadMessage()
			if err != nil {
				return
			}
			if messageType == websocket.BinaryMessage {
				response := "test transcription"
				err = conn.WriteMessage(websocket.TextMessage, []byte(response))
				if err != nil {
					t.Errorf("Failed to write message: %v", err)
					return
				}
			}
		}
	}))
	return wsServer
}

// Test Setup Helpers
// ----------------------------------------

func setupTestHandler(wsURL string) *Handler {
	return NewHandler(&HandlerConfig{
		Timeout:           5 * time.Second,
		WebsocketURL:      wsURL,
		TryToFinalizeText: true,
	})
}

func createTestRequest(method, path, pair, lang string, body io.Reader) *http.Request {
	form := url.Values{}
	form.Add("pair", pair)
	if lang != "" {
		form.Add("lang", lang)
	}
	return httptest.NewRequest(method, path+"?"+form.Encode(), body)
}

// Tests
// ----------------------------------------

func TestHandleUpstreamRequest(t *testing.T) {
	tests := []struct {
		name       string
		path       string
		pairParam  string
		langParam  string
		wantStatus int
	}{
		{
			name:       "valid upstream request",
			path:       "/up",
			pairParam:  "test-pair-1",
			langParam:  "en",
			wantStatus: http.StatusOK,
		},
		{
			name:       "missing pair parameter",
			path:       "/up",
			pairParam:  "",
			langParam:  "en",
			wantStatus: http.StatusOK, // The handler doesn't set status codes explicitly
		},
		{
			name:       "invalid path",
			path:       "/invalid",
			pairParam:  "test-pair-1",
			langParam:  "en",
			wantStatus: http.StatusOK,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			handler := NewHandler(&HandlerConfig{
				Timeout:      5 * time.Second,
				WebsocketURL: "ws://localhost:8080",
			})

			form := url.Values{}
			form.Add("pair", tt.pairParam)
			form.Add("lang", tt.langParam)

			req := httptest.NewRequest(http.MethodPost, tt.path+"?"+form.Encode(), strings.NewReader(""))
			w := httptest.NewRecorder()

			handler.HandleUpstreamRequest(w, req)

			if got := w.Code; got != tt.wantStatus {
				t.Errorf("HandleUpstreamRequest() status = %v, want %v", got, tt.wantStatus)
			}
		})
	}
}

func TestPairContextCreation(t *testing.T) {
	handler := NewHandler(&HandlerConfig{
		Timeout:      5 * time.Second,
		WebsocketURL: "ws://localhost:8080",
	})

	t.Run("creates new pair context", func(t *testing.T) {
		form := url.Values{}
		form.Add("pair", "test-pair-2")
		form.Add("lang", "en")

		req := httptest.NewRequest(http.MethodPost, "/up?"+form.Encode(), strings.NewReader(""))

		pairContext := pairContexts.getOrCreatePairContextForRequest(handler, req)
		if pairContext == nil {
			t.Fatal("expected non-nil pair context")
		}
		if got := pairContext.pair; got != "test-pair-2" {
			t.Errorf("pair = %v, want %v", got, "test-pair-2")
		}
		if got := pairContext.lang; got != "en" {
			t.Errorf("lang = %v, want %v", got, "en")
		}
	})

	t.Run("reuses existing pair context", func(t *testing.T) {
		pair := "test-pair-3"
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		// Create initial pair context
		firstContext := &PairContext{
			pair:      pair,
			audioChan: make(chan []byte, bytesPerChunk),
			results:   make(chan []TextSegment, 10),
			ctx:       ctx,
			cancel:    cancel,
			lang:      "en",
		}
		pairContexts.pairContexts[pair] = firstContext

		// Try to get the same pair context
		form := url.Values{}
		form.Add("pair", pair)
		form.Add("lang", "es") // Different language shouldn't create new context

		req := httptest.NewRequest(http.MethodPost, "/up?"+form.Encode(), strings.NewReader(""))

		secondContext := pairContexts.getOrCreatePairContextForRequest(handler, req)
		if secondContext == nil {
			t.Fatal("expected non-nil pair context")
		}
		if secondContext != firstContext {
			t.Error("expected same context to be reused")
		}
	})
}

func TestPairContextLifecycle(t *testing.T) {
	handler := NewHandler(&HandlerConfig{
		Timeout:      2 * time.Second,
		WebsocketURL: "ws://localhost:8080",
	})

	t.Run("context times out", func(t *testing.T) {
		form := url.Values{}
		form.Add("pair", "test-pair-4")
		form.Add("lang", "en")

		req := httptest.NewRequest(http.MethodPost, "/up?"+form.Encode(), strings.NewReader(""))

		pairContext := pairContexts.getOrCreatePairContextForRequest(handler, req)
		if pairContext == nil {
			t.Fatal("expected non-nil pair context")
		}

		// Wait for timeout
		time.Sleep(3 * time.Second)

		// Context should be done
		select {
		case <-pairContext.ctx.Done():
			// Success
		default:
			t.Error("Context should have timed out")
		}
	})
}

func TestUpDownPairWithWebSocket(t *testing.T) {
	wsServer := setupTestWebSocketServer(t)
	defer wsServer.Close()

	wsURL := "ws" + strings.TrimPrefix(wsServer.URL, "http") + "/"
	handler := setupTestHandler(wsURL)
	pairID := "test-pair-websocket"

	// Start upstream request
	go handleUpstreamRequest(t, handler, pairID)

	// Start downstream request and wait for results
	if err := handleDownstreamRequestAndVerify(t, handler, pairID); err != nil {
		t.Error(err)
	}
}

// Helper functions for TestUpDownPairWithWebSocket
func handleUpstreamRequest(t *testing.T, handler *Handler, pairID string) {
	reader := newInfiniteReader(readTestFile(t, "testdata/16khz.flac"))
	defer reader.Close()

	req := createTestRequest(http.MethodPost, "/up", pairID, "en", reader)
	req.Header.Set("Content-Type", "audio/x-flac; rate=16000")
	req.Header.Set("Transfer-Encoding", "chunked")

	w := httptest.NewRecorder()
	handler.HandleUpstreamRequest(w, req)
}

func handleDownstreamRequestAndVerify(t *testing.T, handler *Handler, pairID string) error {
	receivedText := make(chan string, 1)

	req := createTestRequest(http.MethodGet, "/down", pairID, "", nil)
	req.Header.Set("Connection", "keep-alive")

	pr, pw := io.Pipe()
	downW := &responseRecorder{
		Writer: pw,
		done:   make(chan struct{}),
	}

	go processDownstreamResponse(t, pr, receivedText)
	go func() {
		defer pw.Close()
		handler.HandleDownstreamRequest(downW, req)
		close(downW.done)
	}()

	select {
	case text := <-receivedText:
		t.Logf("Test passed with transcription: %s", text)
		return nil
	case <-time.After(2 * time.Second):
		return fmt.Errorf("timeout waiting for transcription response")
	}
}

func processDownstreamResponse(t *testing.T, pr *io.PipeReader, receivedText chan<- string) {
	defer pr.Close()

	for {
		message, err := readProtobufMessage(pr)
		if err != nil {
			if err != io.EOF {
				t.Errorf("Failed to read message: %v", err)
			}
			return
		}

		fullText := extractFullText(message)
		if strings.Contains(fullText, "test transcription") {
			receivedText <- fullText
			return
		}
	}
}

func readProtobufMessage(r io.Reader) (*google_streaming_api.SpeechRecognitionEvent, error) {
	var length uint32
	if err := binary.Read(r, binary.BigEndian, &length); err != nil {
		return nil, err
	}

	data := make([]byte, length)
	if _, err := io.ReadAtLeast(r, data, int(length)); err != nil {
		return nil, err
	}

	message := &google_streaming_api.SpeechRecognitionEvent{}
	if err := proto.Unmarshal(data, message); err != nil {
		return nil, err
	}

	return message, nil
}

func extractFullText(message *google_streaming_api.SpeechRecognitionEvent) string {
	var fullText string
	for _, result := range message.Result {
		if len(result.Alternative) > 0 {
			fullText += *result.Alternative[0].Transcript
		}
	}
	return fullText
}
