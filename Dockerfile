FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

RUN apt update && apt install -y python3-pip

RUN pip install --upgrade pip
RUN pip install --upgrade setuptools

COPY . /app
WORKDIR /app
RUN pip install .

CMD [ "python3", "-m", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "stt:app", "--workers", "1", "--preload" ]
