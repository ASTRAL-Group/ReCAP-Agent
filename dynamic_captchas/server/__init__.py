from __future__ import annotations

import os

from flask import Flask

from challenges import load_text_captcha_dataset

from .challenge_manager import ChallengeManager
from .routes import create_routes


def create_app() -> Flask:
    """Application factory that wires routes and challenge manager."""
    text_dataset = load_text_captcha_dataset()
    static_seed_env = os.environ.get("CAPTCHA_STATIC_SEED")
    static_seed = None
    if static_seed_env is not None:
        try:
            static_seed = int(static_seed_env, 0)
        except ValueError:
            # If the value cannot be parsed we silently fall back to the default seed.
            static_seed = None

    manager = ChallengeManager(text_dataset, static_seed=static_seed)

    app = Flask(__name__)
    app.register_blueprint(create_routes(manager))

    # Expose manager for other modules (e.g., CLI utilities/tests).
    app.challenge_manager = manager  # type: ignore[attr-defined]
    app.config["DATASET_SIZE"] = manager.dataset_size

    return app
