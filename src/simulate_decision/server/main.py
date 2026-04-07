from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
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

    # Start server in a thread so we can handle signals
    server_config = uvicorn.Config(app, host=host, port=port, reload=False, access_log=False)
    server = uvicorn.Server(server_config)

    def run_server_thread():
        server.run()

    import threading
    server_thread = threading.Thread(target=run_server_thread, daemon=True)
    server_thread.start()

    logger.info(f"Started server on {host}:{port}")

    # Run workers in the main thread
    await run_workers(num_workers=num_workers, max_retries=max_retries)


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
