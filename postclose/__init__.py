"""Post-close performance analysis.

Mount into an existing Flask app with:

    from postclose import register
    register(app)

The blueprint owns the /PostCloseAnalysis prefix and nothing else. It needs a
secret key on the app (upload previews are held in the session) and inherits
whatever before_request auth the host app already applies.
"""
from .routes import bp

__all__ = ["bp", "register"]


def register(app, url_prefix=None):
    app.register_blueprint(bp, url_prefix=url_prefix or bp.url_prefix)
    return app
