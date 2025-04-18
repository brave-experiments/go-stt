package main

import (
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/brave-experiments/go-stt/cr_api_websocket_proxy"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/urfave/cli/v2"
)

// Configuration for the remote WebSocket STT service
const (
	version              = "1"
	defaultListenAddress = "127.0.0.1:8090"
	defaultWebsocketURL  = "ws://127.0.0.1:8080/api-speech-wss/"
)

func main() {
	zerolog.SetGlobalLevel(zerolog.InfoLevel)
	log.Logger = log.Output(
		zerolog.ConsoleWriter{
			Out:     os.Stderr,
			NoColor: true,
		},
	)
	zerolog.CallerMarshalFunc = func(pc uintptr, file string, line int) string {
		short := file
		for i := len(file) - 1; i > 0; i-- {
			if file[i] == '/' {
				short = file[i+1:]
				break
			}
		}
		file = short
		return file + ":" + strconv.Itoa(line)
	}

	zerolog.SetGlobalLevel(zerolog.DebugLevel)
	log.Logger = log.With().Caller().Logger()

	app := cli.NewApp()
	app.Name = "Chromium WebSpeech API Endpoint to WebSocket proxy"
	app.Version = version
	app.Flags = []cli.Flag{
		&cli.StringFlag{
			Name:  "listen-address",
			Value: defaultListenAddress,
		},
		&cli.StringFlag{
			Name:  "websocket-url",
			Value: defaultWebsocketURL,
		},
		&cli.DurationFlag{
			Name:  "timeout",
			Value: 60 * time.Second,
		},
		&cli.BoolFlag{
			Name:  "try-to-finalize-text",
			Value: false,
		},
	}
	app.Action = run

	if err := app.Run(os.Args); err != nil {
		log.Fatal().Err(err)
	}
}

func run(c *cli.Context) error {
	// Create a configuration struct
	config := &cr_api_websocket_proxy.HandlerConfig{
		WebsocketURL:      c.String("websocket-url"),
		Timeout:           c.Duration("timeout"),
		TryToFinalizeText: c.Bool("try-to-finalize-text"),
	}

	// Create a handler instance with the config
	handler := cr_api_websocket_proxy.NewHandler(config)

	// Register handlers that have access to the config
	http.HandleFunc("/up", handler.HandleUpstreamRequest)
	http.HandleFunc("/down", handler.HandleDownstreamRequest)

	http.ListenAndServe(c.String("listen-address"), nil)

	return nil
}
