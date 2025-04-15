docker run --name asr_backend --gpus=all --network tts_backend_net --network-alias web -p 8080:8080 -e DATABASE_URL="mysql+pymysql://root:2002@tts_backend-db:3306/ASR" -e BROKER_URL="redis://tts_backend-redis-1:6379/0" -e BACKEND_URL="redis://tts_backend-redis-1:6379/0"  linh2002/asr_backend_ai:latest
