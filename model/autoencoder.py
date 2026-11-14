"""Small dense autoencoder over a (window x n_signals) block of days. Trained on normal days only;
high reconstruction error = today does not look like this astronaut's normal (plan 4.3 step 4)."""
from __future__ import annotations

from pathlib import Path

import torch
from torch import nn


class WindowAE(nn.Module):
    def __init__(self, window: int, n_signals: int, latent: int = 6):
        super().__init__()
        d = window * n_signals
        self.window, self.n_signals = window, n_signals
        self.enc = nn.Sequential(nn.Flatten(), nn.Linear(d, 32), nn.ReLU(), nn.Linear(32, latent))
        self.dec = nn.Sequential(nn.Linear(latent, 32), nn.ReLU(), nn.Linear(32, d))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.dec(self.enc(x)).view(-1, self.window, self.n_signals)


def errors(model: WindowAE, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Per-window MSE and per-signal squared error (for explainability)."""
    with torch.no_grad():
        se = (model(x) - x) ** 2
    return se.mean(dim=(1, 2)), se.mean(dim=1)


def save(path: Path, model: WindowAE, threshold: float, signals: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state": model.state_dict(), "window": model.window, "signals": signals,
                "threshold": threshold}, path)


def load(path: Path) -> tuple[WindowAE, float, list[str]]:
    ck = torch.load(path, weights_only=True)
    m = WindowAE(ck["window"], len(ck["signals"]))
    m.load_state_dict(ck["state"])
    m.eval()
    return m, ck["threshold"], ck["signals"]
