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

    def configure_dspy(self) -> None:
        import dspy

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
        dspy.settings.configure(lm=lm)

    def _get_extra_kwargs(self) -> dict:
        kwargs = {}
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body
        return kwargs


def get_config() -> EngineConfig:
    return EngineConfig()
