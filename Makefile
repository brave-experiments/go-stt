.PHONY: all build docker serve-docker
all: serve-docker

build:
	python -m bentoml delete -y stt:git || true
	python -m bentoml build --version git src
	cp -R ~/bentoml/bentos/stt/git/* .

docker: build
	docker build -t stt:latest .

serve-docker: docker
	sudo chown -R 1034:1043 models
	docker run -it --rm -p 3000:3000 -v ./models/huggingface:/home/bentoml/.cache/huggingface stt:latest
