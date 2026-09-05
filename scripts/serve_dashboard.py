#!/usr/bin/env python3
"""Serve the hunt dashboard and a live JSON snapshot from data/."""
from __future__ import annotations

import json
import mimetypes
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DASH = ROOT / "dashboard"
PORT = 8765


def _load(name: str, default):
    path = DATA / name
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _score(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def build_snapshot() -> dict:
    deals = _load("best_deals.json", [])
    bundles = _load("best_bundles.json", [])
    pool = _load("bundle_pool.json", [])
    run = _load("last_run.json", {})
    seen = _load("seen_listings.json", {})

    finds_by_id: dict[str, dict] = {}
    for row in deals if isinstance(deals, list) else []:
        if row.get("id") is None:
            continue
        finds_by_id[str(row["id"])] = {
            **row,
            "source": "keep",
            "price_num": _num(row.get("price")),
            "deal_score": _score(row.get("deal_score")),
        }
    for row in (run.get("top") or []):
        if row.get("id") is None:
            continue
        iid = str(row["id"])
        base = finds_by_id.get(iid, {})
        finds_by_id[iid] = {
            **base,
            **{k: v for k, v in row.items() if v is not None},
            "source": base.get("source") or "scored",
            "price_num": _num(row.get("price") if row.get("price") is not None else base.get("price")),
            "deal_score": _score(row.get("deal_score") if row.get("deal_score") is not None else base.get("deal_score")),
            "kept_at": base.get("kept_at"),
        }

    for raw in pool if isinstance(pool, list) else []:
        item = raw.get("item") or {}
        score = raw.get("score") or {}
        if item.get("id") is None:
            continue
        iid = str(item["id"])
        user = item.get("user") or {}
        price = (item.get("price") or {}).get("amount") if isinstance(item.get("price"), dict) else item.get("price")
        existing = finds_by_id.get(iid, {})
        finds_by_id[iid] = {
            **existing,
            "id": item.get("id"),
            "title": item.get("title") or existing.get("title"),
            "price": price if price is not None else existing.get("price"),
            "price_num": _num(price) if price is not None else existing.get("price_num"),
            "currency": ((item.get("price") or {}).get("currency_code")
                         if isinstance(item.get("price"), dict) else existing.get("currency") or "RON"),
            "url": item.get("url") or existing.get("url"),
            "watch": raw.get("watch") or existing.get("watch"),
            "deal_score": _score(score.get("deal_score") if score.get("deal_score") is not None else existing.get("deal_score")),
            "value_band": score.get("value_band") or existing.get("value_band"),
            "scam_risk": score.get("scam_risk") or existing.get("scam_risk"),
            "hunt_fit": score.get("hunt_fit") if score.get("hunt_fit") is not None else existing.get("hunt_fit"),
            "reason": score.get("reason") or existing.get("reason"),
            "seller_id": raw.get("seller_id") or user.get("id") or existing.get("seller_id"),
            "seller": user.get("login") or existing.get("seller"),
            "seller_country": (item.get("_profile") or {}).get("country_code") or existing.get("seller_country"),
            "source": existing.get("source") or "pool",
        }

    finds = list(finds_by_id.values())

    sellers: dict[str, dict] = {}
    def bump(sid, login, country, score, band, is_keep=False, item_id=None):
        if sid is None and not login:
            return
        key = str(sid or login)
        row = sellers.setdefault(key, {
            "seller_id": sid,
            "seller": login,
            "country": country,
            "count": 0,
            "keeps": 0,
            "score_sum": 0,
            "best_score": 0,
            "bands": {},
            "item_ids": set(),
            "watches": set(),
        })
        if login and not row["seller"]:
            row["seller"] = login
        if country and not row["country"]:
            row["country"] = country
        if item_id is not None:
            row["item_ids"].add(str(item_id))
        s = _score(score)
        row["count"] += 1
        row["score_sum"] += s
        row["best_score"] = max(row["best_score"], s)
        if is_keep or band == "steal":
            row["keeps"] += 1
        if band:
            row["bands"][band] = row["bands"].get(band, 0) + 1

    for f in finds:
        bump(
            f.get("seller_id"),
            f.get("seller"),
            f.get("seller_country"),
            f.get("deal_score"),
            f.get("value_band"),
            is_keep=f.get("source") == "keep" or f.get("value_band") in ("steal", "hunt"),
            item_id=f.get("id"),
        )
        if f.get("watch"):
            key = str(f.get("seller_id") or f.get("seller") or "")
            if key in sellers:
                sellers[key]["watches"].add(f["watch"])

    for b in bundles if isinstance(bundles, list) else []:
        if b.get("kind") == "value_haul":
            bump(
                b.get("seller_id"),
                b.get("seller"),
                b.get("country"),
                b.get("deal_score"),
                b.get("value_band"),
                is_keep=b.get("value_band") in ("steal", "hunt"),
            )
        else:
            bump(b.get("seller_id"), b.get("seller"), b.get("country"), 0, None)
        for it in b.get("items") or []:
            bump(
                b.get("seller_id"),
                b.get("seller"),
                b.get("country"),
                it.get("deal_score"),
                "steal" if it.get("role") == "keep" else "hunt",
                is_keep=it.get("role") == "keep",
                item_id=it.get("id"),
            )

    seller_rows = []
    for row in sellers.values():
        n = max(row["count"], 1)
        seller_rows.append({
            "seller_id": row["seller_id"],
            "seller": row["seller"] or f"user {row['seller_id']}",
            "country": row["country"],
            "listings": len(row["item_ids"]) or row["count"],
            "keeps": row["keeps"],
            "avg_score": round(row["score_sum"] / n, 2),
            "best_score": row["best_score"],
            "bands": row["bands"],
            "watches": sorted(row["watches"]),
            "profile_url": (
                f"https://www.vinted.ro/member/{row['seller_id']}"
                if row["seller_id"] else None
            ),
        })
    seller_rows.sort(key=lambda r: (r["best_score"], r["avg_score"], r["keeps"]), reverse=True)

    watches = sorted({f.get("watch") for f in finds if f.get("watch")})
    return {
        "finds": finds,
        "bundles": bundles if isinstance(bundles, list) else [],
        "sellers": seller_rows,
        "watches": watches,
        "run": {
            "finished_at": run.get("finished_at"),
            "scored": run.get("scored"),
            "solo_keeps": run.get("solo_keeps"),
            "bundles": run.get("bundles"),
            "alerts": run.get("alerts"),
            "score_histogram": run.get("score_histogram") or {},
            "seen_keys": len(seen.get("seen_keys") or []),
            "run_count": seen.get("run_count"),
            "last_run": seen.get("last_run"),
        },
        "meta": {
            "source": "local-filesystem",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[dashboard] {self.address_string()} {fmt % args}")

    def _send(self, code: int, body: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/api/dashboard", "/api/dashboard.json"):
            payload = json.dumps(build_snapshot(), ensure_ascii=False).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8")
            return
        if path == "/api/runs":
            payload = json.dumps({"runs": [], "note": "local server — deploy to Vercel for Actions status"}).encode()
            self._send(200, payload, "application/json; charset=utf-8")
            return
        if path in ("/", "/dashboard", "/dashboard/"):
            path = "/index.html"
        elif path.startswith("/dashboard/"):
            path = path[len("/dashboard"):] or "/index.html"

        rel = path.lstrip("/") or "index.html"
        file_path = (DASH / rel).resolve()
        if not str(file_path).startswith(str(DASH.resolve())) or not file_path.is_file():
            self._send(404, b"not found", "text/plain")
            return
        data = file_path.read_bytes()
        ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self._send(200, data, ctype)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/trigger":
            payload = json.dumps({
                "error": "local_only",
                "message": "Triggering Actions requires the Vercel deploy (GITHUB_TOKEN + DASHBOARD_SECRET).",
            }).encode()
            self._send(501, payload, "application/json; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain")


def main():
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Hunt dashboard: http://127.0.0.1:{PORT}/")
    print("API snapshot:    http://127.0.0.1:{}/api/dashboard".format(PORT))
    print("Leave the full-sweep bot alone — this only serves files.")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
