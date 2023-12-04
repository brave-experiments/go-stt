package whisper

import (
	"bytes"
	"errors"
	"regexp"
	"time"
	"net/http"
	"io/ioutil"
	"encoding/binary"
	"encoding/json"

//	"github.com/rs/zerolog/log"
)

const SAMPLE_RATE = 16000

const min_buffer_seconds = 2
const max_buffer_seconds = 15

const MIN_BUFFER_TIME = min_buffer_seconds * time.Second
const MAX_BUFFER_TIME = max_buffer_seconds * time.Second
const MIN_BUFFER_SIZE = min_buffer_seconds * SAMPLE_RATE
const MAX_BUFFER_SIZE = max_buffer_seconds * SAMPLE_RATE

type Transcriber struct {
	transcriber_url string
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

func NewTranscriber(tr_url string, lang string) (*Transcriber, error) {
        return &Transcriber{
			transcriber_url: tr_url,
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

type Response struct {
	Text string `json:"text"`
}

func (t *Transcriber) GetTransciption() (Response, error) {
	var result Response;

	buf := new(bytes.Buffer)
	for _, v := range t.data {
		binary.Write(buf, binary.LittleEndian, v)
	}

	client := &http.Client{}

	req, err := http.NewRequest("POST", t.transcriber_url, buf)
	if err != nil {
		return result, err
	}

	req.Header.Add("Content-Type", "application/octet-stream")
	resp, err := client.Do(req)
	if err != nil {
		return result, err
	}
	defer resp.Body.Close()

	content, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return result, err
	}

	if err := json.Unmarshal(content, &result); err != nil {
		return result, err
	}
	return result, nil
}

func (t *Transcriber) process(force_final bool) ([]TextResult, error) {
	buffer_len := len(t.data)
	buffer_time := time.Second * time.Duration(buffer_len / SAMPLE_RATE)


	if buffer_time < MIN_BUFFER_TIME {
		return nil, errors.New("insufficient data")
	}

	var result []TextResult
	response, err := t.GetTransciption()
	if err != nil {
		return nil, errors.New("failed to transcribe")
	}

	if !force_final && buffer_time < MAX_BUFFER_TIME {
		result = append(result, TextResult{ Text: " " + response.Text, Final: false, })
	} else {
		result = append(result, TextResult{ Text: " " + response.Text, Final: true, })
	}

	if buffer_time >= MAX_BUFFER_TIME {
		t.data = nil
	}

	if result == nil {
		return nil, errors.New("failed to transcribe")
	}

	return result, nil
}

