package cr_api_websocket_proxy

import (
	"fmt"
	"net/http"

	"azul3d.org/engine/audio"
	"github.com/colega/zeropool"

	// Add flac decoder for decoding incoming audio
	_ "azul3d.org/engine/audio/flac"
)

const expectedSampleRate = 16000

const (
	samplesPerChunk = expectedSampleRate / 1000 * 20 // 20ms
	bytesPerChunk   = samplesPerChunk * 2
)

var audioSamplesBufferPool = zeropool.New(
	func() audio.Int16 {
		return make(
			audio.Int16,
			samplesPerChunk,
		)
	},
)

var audioBytesBufferPool = zeropool.New(
	func() []byte {
		return make(
			[]byte,
			bytesPerChunk,
		)
	},
)

func NewAudioDecoder(req *http.Request) (audio.Decoder, error) {
	dec, _, err := audio.NewDecoder(req.Body)
	if err != nil {
		return nil, err
	}

	// Ensure we're working with the correct sample rate
	if dec.Config().SampleRate != expectedSampleRate {
		return nil, fmt.Errorf("unexpected sample rate: %d", dec.Config().SampleRate)
	}

	return dec, nil
}
