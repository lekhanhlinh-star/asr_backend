IMAGE_NAME = asr_backend_ai
TAG = latest
USERNAME = linh2002

build:
	docker build -t $(USERNAME)/$(IMAGE_NAME):$(TAG) .

push:
	docker push $(USERNAME)/$(IMAGE_NAME):$(TAG)

all: build push
