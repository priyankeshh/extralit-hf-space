import sys

from extralit_server.jobs.queues import REDIS_CONNECTION
from rq import Worker

from jobs.pdf_extraction_jobs import extract_pdf_from_s3_job  # noqa: F401


def main():
    queues = []

    # Windows compatibility: use SimpleWorker which doesn't fork
    if sys.platform.startswith("win"):
        from rq import SimpleWorker

        w = SimpleWorker(queues, connection=REDIS_CONNECTION)
        print("🪟 Starting SimpleWorker for Windows compatibility...")
        print(f"📋 Listening on queues: {[q.name for q in queues]}")
    else:
        w = Worker(queues, connection=REDIS_CONNECTION)
        print("🐧 Starting standard Worker...")
        print(f"📋 Listening on queues: {[q.name for q in queues]}")

    w.work(logging_level="INFO")


if __name__ == "__main__":
    main()
