package whisper

import (
	"bytes"
	"errors"
	"regexp"
	"time"
	"net/http"
	"io/ioutil"
	"encoding/binary"

//	"github.com/rs/zerolog/log"
)

const TRANSCRIBER_URL="http://192.168.88.180:3000/process_audio"
const SAMPLE_RATE = 16000

const min_buffer_seconds = 2
const max_buffer_seconds = 15

const MIN_BUFFER_TIME = min_buffer_seconds * time.Second
const MAX_BUFFER_TIME = max_buffer_seconds * time.Second
const MIN_BUFFER_SIZE = min_buffer_seconds * SAMPLE_RATE
const MAX_BUFFER_SIZE = max_buffer_seconds * SAMPLE_RATE

type Transcriber struct {
	data     []float32
	filter   *regexp.Regexp

	Quit       chan bool
	Audio      chan []float32
	Results    chan []TextResult
	Done       chan bool
}

type TextResult struct {
	Text string
	Final bool
}

func NewTranscriber(lang string) (*Transcriber, error) {
        return &Transcriber{
			Quit: make(chan bool, 1),
			Audio: make(chan []float32, 10),
			Results: make(chan []TextResult, 1),
			Done: make(chan bool, 1),
		}, nil
}

func (t* Transcriber) Process() {
	for quit:= false; !quit; {
		select {
			case <-t.Quit:
				results, err := t.process(true)
				if err == nil {
					t.Results <- results
				}
				quit = true
				t.Done <- true
			case samples := <-t.Audio:								
				t.data = append(t.data, samples...)
			default:
				results, err := t.process(false)
				if err == nil {
					t.Results <- results
				} else {
					time.Sleep(1 * time.Second)
				}
		}
	}
}

func (t *Transcriber) process(force_final bool) ([]TextResult, error) {
	buffer_len := len(t.data)
	buffer_time := time.Second * time.Duration(buffer_len / SAMPLE_RATE)


	if buffer_time < MIN_BUFFER_TIME {
		return nil, errors.New("insufficient data")
	}

	var result []TextResult

	client := &http.Client{}
        buf := new(bytes.Buffer)
	for _, v := range t.data {
		binary.Write(buf, binary.LittleEndian, v)
	}
	req, _ := http.NewRequest("POST", TRANSCRIBER_URL, buf)
	req.Header.Add("Content-Type", "application/octet-stream")
	resp, _ := client.Do(req)
	content, _ := ioutil.ReadAll(resp.Body)

	if !force_final && buffer_time < MAX_BUFFER_TIME {
		result = append(result, TextResult{ Text: " " + string(content), Final: false, })
	} else {
		result = append(result, TextResult{ Text: " " + string(content), Final: true, })
	}

	if buffer_time >= MAX_BUFFER_TIME {
		t.data = nil
	}

	if result == nil {
		return nil, errors.New("failed to transcribe")
	}

	return result, nil
}

