.PHONY: all build docker serve-docker
all: serve-docker

docker: build
	docker build -t stt:latest .

serve-docker: docker
	docker run -it --rm -p 3000:3000 -v ./models/huggingface:/home/bentoml/.cache/huggingface stt:latest
