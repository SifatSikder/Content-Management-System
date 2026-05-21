"""Background jobs — arq worker functions.

Run as a separate process from the FastAPI app via `make dev-worker`. Each
job module exports thin async functions; complex orchestration stays in
the services layer. The worker entrypoint is `app.jobs.worker.WorkerSettings`.
"""
