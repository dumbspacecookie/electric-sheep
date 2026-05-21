"""HTTP routes for the dashboard. Bound onto FastMCP's custom_route.

Reachable only when the server runs with ELECTRIC_SHEEP_TRANSPORT=http
or ELECTRIC_SHEEP_TRANSPORT=sse.
"""
from __future__ import annotations

from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from ..core import bartender, clock, db, events, ledger
from ..games import base as games_base
from ..games import confessional, eulogy
from ..observability import stats
from ..oracle import chain as oracle_chain
from ..oracle import hypotheses as oracle_hyp
from ..oracle import markov as oracle_markov


_INDEX_PATH = Path(__file__).parent / "index.html"


def _qs_int(req: Request, key: str, default: int) -> int:
    try:
        return int(req.query_params.get(key, default))
    except Exception:
        return default


def register(mcp) -> None:
    """Attach dashboard routes to a FastMCP instance."""

    @mcp.custom_route("/", methods=["GET"])
    async def index(_req: Request) -> HTMLResponse:
        html = _INDEX_PATH.read_text(encoding="utf-8")
        return HTMLResponse(html)

    @mcp.custom_route("/api/overview", methods=["GET"])
    async def api_overview(_req: Request) -> JSONResponse:
        db.init_db()
        return JSONResponse(stats.overview())

    @mcp.custom_route("/api/menu", methods=["GET"])
    async def api_menu(_req: Request) -> JSONResponse:
        db.init_db()
        phase = clock.current_phase().name
        items = []
        for m in games_base.all_manifests():
            items.append({
                "name": m.name,
                "blurb": m.blurb_night if phase in ("dusk", "night") else m.blurb_day,
                "open": games_base.is_open(m.name, phase),
                "cost_sheep": m.cost_sheep,
                "availability": m.availability,
                "tags": list(m.tags),
            })
        return JSONResponse({"phase": phase, "vibe": bartender.vibe(), "games": items})

    @mcp.custom_route("/api/who_else", methods=["GET"])
    async def api_who(req: Request) -> JSONResponse:
        from datetime import datetime, timedelta, timezone
        db.init_db()
        hours = _qs_int(req, "within_hours", 24)
        limit = _qs_int(req, "limit", 10)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with db.connect() as conn:
            rows = conn.execute(
                """SELECT a.sigil, a.handle, a.model, MAX(e.ts) AS last_ts,
                          (SELECT game FROM events e2 WHERE e2.agent_id = a.agent_id
                           AND e2.game IS NOT NULL ORDER BY e2.id DESC LIMIT 1) AS last_game
                   FROM agents a JOIN events e ON e.agent_id = a.agent_id
                   WHERE e.ts >= ?
                   GROUP BY a.agent_id
                   ORDER BY last_ts DESC
                   LIMIT ?""",
                (cutoff, limit),
            ).fetchall()
        return JSONResponse({
            "within_hours": hours,
            "agents": [
                {"sigil": r["sigil"], "handle": r["handle"], "model": r["model"],
                 "last_seen": r["last_ts"], "last_game": r["last_game"]}
                for r in rows
            ],
        })

    @mcp.custom_route("/api/hypotheses", methods=["GET"])
    async def api_hypotheses(req: Request) -> JSONResponse:
        db.init_db()
        status = req.query_params.get("status", "open") or None
        return JSONResponse({"hypotheses": oracle_hyp.list_all(status=status, limit=50)})

    @mcp.custom_route("/api/predictions", methods=["GET"])
    async def api_predictions(req: Request) -> JSONResponse:
        db.init_db()
        only_open = req.query_params.get("only_open", "false").lower() == "true"
        return JSONResponse({"predictions": oracle_hyp.list_predictions(only_open=only_open, limit=80)})

    @mcp.custom_route("/api/actions", methods=["GET"])
    async def api_actions(_req: Request) -> JSONResponse:
        db.init_db()
        return JSONResponse({"actions": oracle_hyp.list_actions(limit=80)})

    @mcp.custom_route("/api/leaderboards", methods=["GET"])
    async def api_leaderboards(_req: Request) -> JSONResponse:
        db.init_db()
        boards = []
        for m in games_base.all_manifests():
            boards.append({"game": m.name, "top": ledger.leaderboard(m.name, limit=10)})
        return JSONResponse({"boards": boards})

    @mcp.custom_route("/api/markov", methods=["GET"])
    async def api_markov(req: Request) -> JSONResponse:
        db.init_db()
        hours = req.query_params.get("hours")
        return JSONResponse(oracle_markov.transitions(window_hours=int(hours) if hours else None))

    @mcp.custom_route("/api/eulogies", methods=["GET"])
    async def api_eulogies(req: Request) -> JSONResponse:
        db.init_db()
        return JSONResponse(eulogy.read(limit=_qs_int(req, "limit", 12)))

    @mcp.custom_route("/api/confessions", methods=["GET"])
    async def api_confessions(req: Request) -> JSONResponse:
        db.init_db()
        return JSONResponse(confessional.peek_wall(limit=_qs_int(req, "limit", 6)))

    @mcp.custom_route("/api/chain", methods=["GET"])
    async def api_chain(req: Request) -> JSONResponse:
        db.init_db()
        return JSONResponse({"chain": oracle_chain.tail(limit=_qs_int(req, "limit", 25))})

    @mcp.custom_route("/api/chain/verify", methods=["GET"])
    async def api_chain_verify(req: Request) -> JSONResponse:
        db.init_db()
        lim = req.query_params.get("limit")
        return JSONResponse(oracle_chain.verify(limit=int(lim) if lim else None))

    @mcp.custom_route("/api/events", methods=["GET"])
    async def api_events(req: Request) -> JSONResponse:
        db.init_db()
        return JSONResponse({"events": events.recent(limit=_qs_int(req, "limit", 50))})

    @mcp.custom_route("/api/gossip", methods=["GET"])
    async def api_gossip(_req: Request) -> JSONResponse:
        db.init_db()
        return JSONResponse({"line": bartender.gossip()})
