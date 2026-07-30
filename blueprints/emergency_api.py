"""Break-glass SQL endpoint, deliberately isolated from the normal API."""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text

from models import EmergencyApiAudit, EmergencyApiToken, db

bp = Blueprint("emergency_api", __name__, url_prefix="/api/emergency")


def _audit(token, sql: str, success: bool, row_count=None, error=None):
    db.session.add(EmergencyApiAudit(
        token_id=token.id if token else None,
        remote_addr=request.remote_addr,
        sql_fingerprint=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        success=success, row_count=row_count, error=(error or "")[:300],
    ))
    db.session.commit()


@bp.post("/sql")
def execute_sql():
    if not current_app.config["EMERGENCY_SQL_API_ENABLED"]:
        return jsonify(error="emergency API disabled"), 404
    raw_body = request.get_data(cache=True)
    try:
        payload = request.get_json(force=True)
        sql = (payload.get("sql") or "").strip()
    except Exception:
        return jsonify(error="invalid JSON"), 400
    token_value = request.headers.get("X-Emergency-Token", "")
    timestamp = request.headers.get("X-Emergency-Timestamp", "")
    signature = request.headers.get("X-Emergency-Signature", "")
    try:
        stamp = datetime.utcfromtimestamp(int(timestamp))
    except (TypeError, ValueError, OverflowError):
        _audit(None, sql, False, error="invalid timestamp")
        return jsonify(error="invalid timestamp"), 401
    if abs((datetime.utcnow() - stamp).total_seconds()) > 60:
        _audit(None, sql, False, error="expired request")
        return jsonify(error="expired request"), 401
    token = EmergencyApiToken.query.filter_by(token_hash=hashlib.sha256(token_value.encode()).hexdigest()).first()
    if not token or token.revoked_at or token.expires_at <= datetime.utcnow():
        _audit(None, sql, False, error="invalid or expired token")
        return jsonify(error="invalid or expired token"), 401
    expected = hmac.new(token_value.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        _audit(token, sql, False, error="invalid signature")
        return jsonify(error="invalid signature"), 401
    if not sql or len(sql) > 100_000 or "\x00" in sql:
        _audit(token, sql, False, error="invalid SQL payload")
        return jsonify(error="invalid SQL payload"), 400
    try:
        result = db.session.execute(text(sql))
        rows = [dict(row) for row in result.mappings().fetchmany(1000)] if result.returns_rows else []
        row_count = result.rowcount
        db.session.commit()
        token.last_used_at = datetime.utcnow(); db.session.commit()
        _audit(token, sql, True, row_count=row_count)
        return jsonify(ok=True, rows=rows, row_count=row_count, truncated=result.returns_rows and len(rows) == 1000)
    except Exception as exc:
        db.session.rollback()
        _audit(token, sql, False, error=str(exc))
        return jsonify(error="SQL execution failed"), 400
