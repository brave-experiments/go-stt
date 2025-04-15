//go:build !wav_write

package cr_api_websocket_proxy

// Empty implementations for release builds

type wavFileWriter struct{}

func initWavWriter(writer **wavFileWriter, pairID string) {
	// Do nothing in release builds
}

func writeToWavFile(writer *wavFileWriter, audioBytes []byte) {
	// Do nothing in release builds
}

func closeWavWriter(writer *wavFileWriter) {
	// Do nothing in release builds
}
