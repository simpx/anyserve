"""
llama.cpp configuration.
"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class LlamaCppConfig:
    """llama.cpp built-in Worker configuration."""

    # Model path (required)
    model_path: str = ""

    # Model name (for API)
    name: str = "default"

    # Model loading parameters
    n_ctx: int = 2048
    n_gpu_layers: int = -1
    n_batch: int = 512
    n_threads: Optional[int] = None

    # Generation parameter defaults
    max_tokens: int = 256
    temperature: float = 0.7
    top_p: float = 0.95
    top_k: int = 40
    repeat_penalty: float = 1.1
    stop: list[str] = field(default_factory=list)

    # Service parameters
    host: str = "0.0.0.0"
    port: int = 8000

    # OpenAI server parameters (embedded)
    openai_port: Optional[int] = None  # None = disabled
    openai_host: str = "0.0.0.0"

    @classmethod
    def from_yaml(cls, path: str) -> "LlamaCppConfig":
        """Load configuration from a YAML file."""
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def validate(self) -> None:
        """Validate configuration."""
        if not self.model_path:
            raise ValueError("model_path is required")
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        if self.n_ctx < 1:
            raise ValueError("n_ctx must be positive")
        if self.port < 1 or self.port > 65535:
            raise ValueError("port must be between 1 and 65535")
        if self.openai_port is not None and (self.openai_port < 1 or self.openai_port > 65535):
            raise ValueError("openai_port must be between 1 and 65535")
