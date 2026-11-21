"""
Audit recording helper service for TenderBee.
Provides centralized logging of security, domain, and data lifecycle events,
as well as tamper-evident hash-chained event logging.
"""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from apps.accounts.models import Organization
from apps.audit.models import AuditEventType, AuditLogEntry


def record_audit_event(
    organization: Organization,
    actor: str,
    event_type: str,
    target_id: str,
    details: Optional[Dict[str, Any]] = None,
) -> AuditLogEntry:
    """
    Creates an immutable audit log entry scoped to the given organization.
    """
    if not organization:
        raise ValueError("Audit event requires a valid Organization tenant.")
        
    return AuditLogEntry.objects.create(
        organization=organization,
        actor=actor or "system",
        event_type=event_type,
        target_id=str(target_id),
        details=details or {},
    )


class AuditTrailService:
    """Service wrapper for logging, querying, and hash-chaining audit events."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path(__file__).resolve().parents[3] / "data" / "tenderbee.db"
        self._init_db()

    def _init_db(self):
        """Initializes append-only audit trail table."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_hash TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()

    def _get_last_event_hash(self, organization_id: str) -> str:
        """Retrieves previous event hash for block chaining."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT event_hash FROM audit_events
                WHERE organization_id = ?
                ORDER BY event_id DESC LIMIT 1
            """, (organization_id,))
            row = cursor.fetchone()
            return row[0] if row else "GENESIS_HASH_00000000000000000000000000000000"

    def log_event(
        self,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        payload: Dict[str, Any],
        organization_id: str = "org_default",
    ) -> Dict[str, Any]:
        """
        Appends an immutable, tamper-evident audit event.
        Computes SHA-256 over: prev_hash + actor + action + entity + payload + timestamp.
        """
        prev_hash = self._get_last_event_hash(organization_id)
        timestamp = datetime.now(timezone.utc).isoformat()
        payload_str = json.dumps(payload, sort_keys=True)

        event_data = f"{prev_hash}|{organization_id}|{actor}|{action}|{entity_type}|{entity_id}|{payload_str}|{timestamp}"
        event_hash = hashlib.sha256(event_data.encode("utf-8")).hexdigest()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_events (
                    event_hash, prev_hash, organization_id, actor, action,
                    entity_type, entity_id, payload_json, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_hash, prev_hash, organization_id, actor, action,
                entity_type, entity_id, payload_str, timestamp
            ))
            conn.commit()

        return {
            "success": True,
            "event_hash": event_hash,
            "prev_hash": prev_hash,
            "timestamp": timestamp,
        }

    def get_events(
        self,
        entity_id: Optional[str] = None,
        organization_id: str = "org_default",
    ) -> List[Dict[str, Any]]:
        """Retrieves events for an entity or organization."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if entity_id:
                cursor.execute("""
                    SELECT * FROM audit_events
                    WHERE organization_id = ? AND entity_id = ?
                    ORDER BY event_id ASC
                """, (organization_id, entity_id))
            else:
                cursor.execute("""
                    SELECT * FROM audit_events
                    WHERE organization_id = ?
                    ORDER BY event_id ASC
                """, (organization_id,))

            rows = cursor.fetchall()
            return [
                {
                    "event_id": r["event_id"],
                    "event_hash": r["event_hash"],
                    "prev_hash": r["prev_hash"],
                    "actor": r["actor"],
                    "action": r["action"],
                    "entity_type": r["entity_type"],
                    "entity_id": r["entity_id"],
                    "payload": json.loads(r["payload_json"]),
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]

    @staticmethod
    def record_event(organization, actor, event_type, target_id, details=None):
        return record_audit_event(organization, actor, event_type, target_id, details)
