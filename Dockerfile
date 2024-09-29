FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ENV NVIDIA_VISIBLE_DEVICES=all

RUN apt update && apt install -y python3-pip

RUN pip install --upgrade pip
RUN pip install --upgrade setuptools

COPY ./requirements.txt ./requirements.txt

RUN pip install -r requirements.txt

COPY . /app
WORKDIR /app
RUN pip install .

EXPOSE 3000

CMD [ "python3", "-m", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "stt:app", "--workers", "1", "-b", "0.0.0.0:3000"]
