from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
import json

import uvicorn

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format=json.dumps({
        "timestamp": "%(asctime)s",
        "level": "%(levelname)s",
        "logger": "%(name)s",
        "message": "%(message)s"
    }) if os.getenv("LOG_FORMAT") == "json" else "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    from simulate_decision.server.api import app

    logger.info(f"Starting SimulateDecision API server on {host}:{port}")

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        reload=False,
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


async def run_workers(num_workers: int = 2, max_retries: int = 3) -> None:
    from simulate_decision.server.worker import run_workers as start_workers

    logger.info(f"Starting {num_workers} worker(s)")
    await start_workers(num_workers=num_workers, max_retries=max_retries)


async def run_all(
    host: str = "0.0.0.0",
    port: int = 8000,
    num_workers: int = 2,
    max_retries: int = 3,
) -> None:
    from simulate_decision.server.api import app
    from simulate_decision.server.worker import run_workers as start_workers

    # Start server in a thread so we can handle signals
    server_config = uvicorn.Config(
        app,
        host=host,
        port=port,
        reload=False,
        access_log=False,
        log_level="info"
    )
    server = uvicorn.Server(server_config)

    def run_server_thread():
        server.run()

    import threading
    server_thread = threading.Thread(target=run_server_thread, daemon=True)
    server_thread.start()

    logger.info(f"Started server on {host}:{port}")

    # Set up graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        shutdown_event.set()

    import signal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start workers
        worker_task = asyncio.create_task(start_workers(num_workers=num_workers, max_retries=max_retries))

        # Create task for shutdown event
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Wait for shutdown signal or worker completion
        done, pending = await asyncio.wait([shutdown_task, worker_task], return_when=asyncio.FIRST_COMPLETED)

        if shutdown_event.is_set():
            logger.info("Shutdown signal received, stopping workers...")
            # Give workers time to finish current jobs
            await asyncio.sleep(5)
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

        # Cancel any remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info("Shutdown complete")

    except Exception as e:
        logger.error(f"Error during server operation: {e}")
        raise


def signal_handler(sig, frame) -> None:
    logger.info("Shutdown signal received")
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="SimulateDecision Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    parser.add_argument("--workers", type=int, default=2, help="Number of workers")
    parser.add_argument("--max-retries", type=int, default=3, help="Max job retries")
    parser.add_argument("--server-only", action="store_true", help="Run API only (no workers)")
    parser.add_argument("--workers-only", action="store_true", help="Run workers only (no API)")

    args = parser.parse_args()

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        if args.server_only:
            run_server(host=args.host, port=args.port)
        elif args.workers_only:
            asyncio.run(run_workers(num_workers=args.workers, max_retries=args.max_retries))
        else:
            asyncio.run(
                run_all(
                    host=args.host,
                    port=args.port,
                    num_workers=args.workers,
                    max_retries=args.max_retries,
                )
            )
    except KeyboardInterrupt:
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
