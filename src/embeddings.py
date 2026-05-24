from __future__ import annotations

import numpy as np

_embedder_cache: dict[str, "Embedder"] = {}


def get_embedder(model_name: str, device: str = "cpu") -> "Embedder":
    key = f"{model_name}:{device}"
    if key not in _embedder_cache:
        _embedder_cache[key] = Embedder(model_name, device)
    return _embedder_cache[key]


class Embedder:
    def __init__(self, model_name: str, device: str = "cpu"):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, device=device)

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        vectors = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 50,
        )
        return np.asarray(vectors, dtype=np.float32)
