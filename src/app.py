# src/app.py
from flask import Flask, jsonify
from .api.routes import bp
from .utils.logging import get_logger
from .domain.errors import AppError

# NOTE: your file is metrics/router.py (not routes.py), so import from router
from .metrics.router import metrics_bp  # <-- new

log = get_logger(__name__)

def create_app():
    app = Flask(__name__)

    # existing API
    app.register_blueprint(bp)

    # expose /metrics/<symbol> on the SAME server (port 5002)
    app.register_blueprint(metrics_bp, url_prefix="/metrics")  # <-- new

    @app.errorhandler(AppError)
    def handle_app_error(err: AppError):
        log.warning(f"AppError: {err.message}")
        return jsonify({"error": err.message}), err.status_code

    @app.errorhandler(Exception)
    def handle_unexpected(e):
        log.exception("Unhandled error")
        return jsonify({"error": "internal_error"}), 500

    return app

# For `flask run`
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
