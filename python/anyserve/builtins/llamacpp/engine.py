"""
llama.cpp engine wrapper.
"""

from typing import Iterator, Optional

from llama_cpp import Llama

from .config import LlamaCppConfig


class LlamaCppEngine:
    """llama.cpp engine wrapper."""

    def __init__(self, config: LlamaCppConfig):
        self.config = config
        self._model: Optional[Llama] = None

    def load(self) -> None:
        """Load the model."""
        self._model = Llama(
            model_path=self.config.model_path,
            n_ctx=self.config.n_ctx,
            n_gpu_layers=self.config.n_gpu_layers,
            n_batch=self.config.n_batch,
            n_threads=self.config.n_threads,
            verbose=False,
        )

    @property
    def model(self) -> Llama:
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load() first.")
        return self._model

    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        stop: Optional[list[str]] = None,
    ) -> str:
        """Generate text (non-streaming)."""
        result = self.model(
            prompt,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature if temperature is not None else self.config.temperature,
            top_p=top_p if top_p is not None else self.config.top_p,
            top_k=top_k if top_k is not None else self.config.top_k,
            repeat_penalty=repeat_penalty if repeat_penalty is not None else self.config.repeat_penalty,
            stop=stop or self.config.stop or None,
            echo=False,
        )
        return result["choices"][0]["text"]

    def generate_stream(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        stop: Optional[list[str]] = None,
    ) -> Iterator[str]:
        """Generate text (streaming)."""
        for chunk in self.model(
            prompt,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature if temperature is not None else self.config.temperature,
            top_p=top_p if top_p is not None else self.config.top_p,
            top_k=top_k if top_k is not None else self.config.top_k,
            repeat_penalty=repeat_penalty if repeat_penalty is not None else self.config.repeat_penalty,
            stop=stop or self.config.stop or None,
            echo=False,
            stream=True,
        ):
            yield chunk["choices"][0]["text"]
