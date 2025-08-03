elastic: /usr/share/elasticsearch/bin/elasticsearch
redis: /usr/bin/redis-server
worker_high: sleep 30; rq worker-pool --num-workers 2 high
worker_default: sleep 30; rq worker-pool --num-workers 1 default
argilla: sleep 30; /bin/bash start_argilla_server.sh
extract-api: sleep 30; uvicorn app:app --host 0.0.0.0 --port 9229
