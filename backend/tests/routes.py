"""Every API route with its full path.

FastAPI 0.151 wraps included routers lazily, so `app.routes` holds only the top-level
entries; iter_route_contexts() expands them.
"""

from fastapi.routing import APIRoute, iter_route_contexts

from app.main import app


def api_routes() -> list[tuple[str, APIRoute]]:
    routes = [
        (ctx.path, ctx.original_route)
        for ctx in iter_route_contexts(app.routes)
        if isinstance(ctx.original_route, APIRoute) and ctx.path
    ]
    # Guard against this helper silently finding nothing again.
    assert len(routes) > 50, len(routes)
    return routes
