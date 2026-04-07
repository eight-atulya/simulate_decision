from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_loaded = False
except ImportError:
    _env_loaded = None


def _load_env() -> None:
    global _env_loaded
    if _env_loaded is False:
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        _env_loaded = True


_load_env()


@dataclass
class EngineConfig:
    lm_studio_url: str = field(
        default_factory=lambda: os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
    )
    api_key: str = field(
        default_factory=lambda: os.getenv("LM_STUDIO_API_KEY", "lm-studio")
    )
    max_iterations: int = field(
        default_factory=lambda: int(os.getenv("MAX_ITERATIONS", "3"))
    )
    model_name: str = field(
        default_factory=lambda: os.getenv("MODEL_NAME", "lmstudio/google/gemma-4-26b-a4b")
    )
    signal_loss_threshold: int = field(
        default_factory=lambda: int(os.getenv("SIGNAL_LOSS_THRESHOLD", "3"))
    )
    extra_body: dict = field(default_factory=lambda: {"response_format": {"type": "text"}})
    timeout: int = field(default_factory=lambda: int(os.getenv("TIMEOUT", "300")))

    def validate(self) -> None:
        """Validate configuration values"""
        if not self.lm_studio_url.startswith(('http://', 'https://')):
            raise ValueError("LM_STUDIO_URL must be a valid HTTP/HTTPS URL")

        if not self.api_key or self.api_key == "lm-studio":
            logger.warning("Using default API key - ensure this is set in production")

        if self.max_iterations < 1 or self.max_iterations > 20:
            raise ValueError("MAX_ITERATIONS must be between 1 and 20")

        if self.signal_loss_threshold < 1:
            raise ValueError("SIGNAL_LOSS_THRESHOLD must be at least 1")

        if self.timeout < 10:
            raise ValueError("TIMEOUT must be at least 10 seconds")

    def configure_dspy(self) -> None:
        import dspy
        import logging

        # Validate config before configuring DSPy
        self.validate()

        # Enable full DSPy logging
        dspy.enable_logging()
        dspy.enable_litellm_logging()
        
        # Configure Python logging for dspy
        logging.getLogger("dspy").setLevel(logging.DEBUG)
        logging.getLogger("litellm").setLevel(logging.WARNING)  # Less verbose for LiteLLM

        model_name = self.model_name
        if model_name.startswith("lmstudio/"):
            model_name = model_name.replace("lmstudio/", "")

        lm = dspy.LM(
            f"openai/{model_name}",
            api_base=self.lm_studio_url,
            api_key=self.api_key,
            model_type="chat",
            timeout=self.timeout,
            **self._get_extra_kwargs(),
        )
        dspy.settings.configure(
            lm=lm,
            provide_traceback=True,  # Include Python tracebacks in error logs
            track_usage=True,        # Record token counts for every LM call
            max_trace_size=10000,    # Store all trace entries
            max_history_size=10000,  # Store all LM interactions
            disable_history=False,   # Enable history recording
        )

    def _get_extra_kwargs(self) -> dict:
        kwargs = {}
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body
        return kwargs


def get_config() -> EngineConfig:
    return EngineConfig()
