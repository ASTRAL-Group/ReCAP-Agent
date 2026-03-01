#!/usr/bin/env python3
"""
Flask entrypoint for the dynamic CAPTCHA server.
"""

import os

from server import create_app

app = create_app()


if __name__ == "__main__":
    dataset_size = app.config.get("DATASET_SIZE", 0)
    print("Starting Flask application...\n")
    print("Available CAPTCHA types:")
    print("  • Random: http://localhost:5000/challenge")
    print("  • Text: http://localhost:5000/challenge/text")
    print("  • Compact: http://localhost:5000/challenge/compact")
    print("  • Icon Selection: http://localhost:5000/challenge/icon")
    print("  • Paged: http://localhost:5000/challenge/paged")
    print("  • Icon Match: http://localhost:5000/challenge/icon-match")
    print("  • Slider: http://localhost:5000/challenge/slider")
    print("  • Image Grid: http://localhost:5000/challenge/image_grid")
    debug_mode = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes", "on"}
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)