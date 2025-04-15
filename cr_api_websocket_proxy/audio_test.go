package cr_api_websocket_proxy

import (
	"bytes"
	"io"
	"net/http"
	"os"
	"testing"

	"azul3d.org/engine/audio"
)

func TestAudioBufferPools(t *testing.T) {
	t.Run("samples buffer pool", func(t *testing.T) {
		samples := audioSamplesBufferPool.Get()
		if samples == nil {
			t.Error("expected non-nil samples buffer")
		}
		if got := len(samples); got != samplesPerChunk {
			t.Errorf("samples buffer length = %v, want %v", got, samplesPerChunk)
		}

		audioSamplesBufferPool.Put(samples)
	})

	t.Run("bytes buffer pool", func(t *testing.T) {
		buffer := audioBytesBufferPool.Get()
		if buffer == nil {
			t.Error("expected non-nil bytes buffer")
		}
		if got := len(buffer); got != bytesPerChunk {
			t.Errorf("bytes buffer length = %v, want %v", got, bytesPerChunk)
		}

		audioBytesBufferPool.Put(buffer)
	})
}

type mockBody struct {
	*bytes.Buffer
}

func (m mockBody) Close() error {
	return nil
}

func TestFlacDecoder_InvalidData(t *testing.T) {
	t.Run("invalid audio data", func(t *testing.T) {
		req := &http.Request{
			Body: mockBody{bytes.NewBuffer([]byte("invalid audio data"))},
		}

		decoder, err := NewAudioDecoder(req)
		if err == nil {
			t.Error("expected error for invalid audio data")
		}
		if decoder != nil {
			t.Error("expected nil decoder for invalid audio data")
		}
	})
}

func TestFlacDecoder_ValidData(t *testing.T) {
	req := &http.Request{
		Body: mockBody{bytes.NewBuffer(readTestFile(t, "testdata/16khz.flac"))},
	}

	decoder, err := NewAudioDecoder(req)
	if err != nil {
		t.Fatalf("failed to create decoder: %v", err)
	}

	// Verify decoder config
	config := decoder.Config()
	if config.SampleRate != expectedSampleRate {
		t.Errorf("sample rate = %v, want %v", config.SampleRate, expectedSampleRate)
	}

	// Try reading some samples
	samples := make(audio.Int16, 1024)
	n, err := decoder.Read(samples)
	if err != nil && err != io.EOF {
		t.Errorf("failed to read samples: %v", err)
	}
	if n == 0 {
		t.Error("expected to read some samples")
	}
}

func TestFlacDecoder_InvalidSampleRate(t *testing.T) {
	req := &http.Request{
		Body: mockBody{bytes.NewBuffer(readTestFile(t, "testdata/8khz.flac"))},
	}

	decoder, err := NewAudioDecoder(req)
	if decoder != nil {
		t.Error("expected nil decoder for invalid sample rate")
	}
	if err == nil {
		t.Error("expected error for invalid sample rate")
	}
}

// Helper to read test file contents
func readTestFile(t *testing.T, path string) []byte {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("failed to read test file %s: %v", path, err)
	}
	return data
}
