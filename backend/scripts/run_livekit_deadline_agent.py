"""Run the separately deployed LiveKit reminder worker.

From the repository root: python -m backend.scripts.run_livekit_deadline_agent dev
"""
from backend.app.services.assistant_livekit_agent import cli, server

if __name__ == "__main__":
    cli.run_app(server)
