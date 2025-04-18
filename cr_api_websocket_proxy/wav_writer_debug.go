//go:build wav_write

package cr_api_websocket_proxy

import (
	"encoding/binary"
	"os"
	"time"

	"github.com/rs/zerolog/log"
)

type wavFileWriter struct {
	file *os.File
}

func initWavWriter(writer **wavFileWriter, pairID string) {
	// Create WAV file with timestamp name
	timestamp := time.Now().Format("20060102-150405")
	filename := timestamp + ".wav"
	f, err := os.OpenFile(filename, os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Error().Err(err).Msgf("[%s] Failed to create WAV file", pairID)
		return
	}

	// Write WAV header if file is new (size 0)
	info, _ := f.Stat()
	if info.Size() == 0 {
		header := []byte{
			'R', 'I', 'F', 'F', // ChunkID
			0, 0, 0, 0, // ChunkSize (to be updated on close)
			'W', 'A', 'V', 'E', // Format
			'f', 'm', 't', ' ', // Subchunk1ID
			16, 0, 0, 0, // Subchunk1Size
			1, 0, // AudioFormat (PCM)
			1, 0, // NumChannels (Mono)
			0x80, 0x3E, 0, 0, // SampleRate (16000)
			0x00, 0x7D, 0, 0, // ByteRate
			2, 0, // BlockAlign
			16, 0, // BitsPerSample
			'd', 'a', 't', 'a', // Subchunk2ID
			0, 0, 0, 0, // Subchunk2Size (to be updated on close)
		}
		f.Write(header)
	}

	*writer = &wavFileWriter{file: f}
	log.Info().Msgf("[%s] WAV recording started: %s", pairID, filename)
}

func writeToWavFile(writer *wavFileWriter, audioBytes []byte) {
	if writer != nil && writer.file != nil {
		writer.file.Write(audioBytes)
	}
}

func closeWavWriter(writer *wavFileWriter) {
	if writer == nil || writer.file == nil {
		return
	}

	log.Info().Msg("Closing WAV file")
	f := writer.file

	// Update WAV header with final sizes before closing
	f.Sync()
	f.Seek(0, 0)
	info, _ := f.Stat()
	fileSize := info.Size()
	log.Info().Msgf("File size: %d", fileSize)

	// Update ChunkSize
	chunkSize := uint32(fileSize - 8)
	f.Seek(4, 0)
	binary.Write(f, binary.LittleEndian, chunkSize)

	// Update Subchunk2Size
	dataSize := uint32(fileSize - 44)
	f.Seek(40, 0)
	binary.Write(f, binary.LittleEndian, dataSize)

	f.Close()
	writer.file = nil
}
