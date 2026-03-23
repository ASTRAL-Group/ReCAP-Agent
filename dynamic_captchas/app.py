#!/usr/bin/env python3
"""
Flask entrypoint for the dynamic CAPTCHA server.
"""

import os

from server import create_app

app = create_app()


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    local_base = f"http://localhost:{port}"

    print("Starting Flask application...\n")
    print("Available CAPTCHA types:")
    print(f"  • Random: {local_base}/challenge")
    print(f"  • Text: {local_base}/challenge/text")
    print(f"  • Compact: {local_base}/challenge/compact")
    print(f"  • Icon Selection: {local_base}/challenge/icon")
    print(f"  • Paged: {local_base}/challenge/paged")
    print(f"  • Icon Match: {local_base}/challenge/icon-match")
    print(f"  • Slider: {local_base}/challenge/slider")
    print(f"  • Image Grid: {local_base}/challenge/image_grid")

    app.run(debug=_env_flag("FLASK_DEBUG"), host=host, port=port)
