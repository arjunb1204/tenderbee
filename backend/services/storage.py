"""
Production-level storage engine for TenderBee Tenders and Snapshots.
Supports Multi-tenant isolation, SHA-256 immutability, and tiered storage
(SQLite/PostgreSQL metadata + Local/S3 object storage for raw payloads).
"""
import os
import json
import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path


class TenderStorage:
    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            # Dynamically locate the repository data directory: <repo_root>/data
            self.base_dir = Path(__file__).resolve().parents[2] / "data"
            
        self.snapshots_dir = self.base_dir / "snapshots"
        self.db_path = self.base_dir / "tenderbee.db"
        
        # Ensure directories exist
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initializes relational tables with organization_id tenant isolation."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 1. Tender Master Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tenders (
                    tender_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    buyer_name TEXT,
                    submission_deadline TEXT,
                    estimated_value_inr REAL,
                    source_url TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # 2. Immutable Tender Snapshots (Corrigendum tracking via SHA-256)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tender_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    tender_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    raw_payload_path TEXT NOT NULL,
                    extracted_json_path TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    FOREIGN KEY (tender_id) REFERENCES tenders (tender_id)
                )
            """)
            
            # 3. Versioned Rule Packs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rule_packs (
                    rule_pack_id TEXT PRIMARY KEY,
                    tender_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    rules_json TEXT NOT NULL,
                    confirmed_by TEXT,
                    confirmed_at TEXT,
                    FOREIGN KEY (tender_id) REFERENCES tenders (tender_id)
                )
            """)

            # Add search & discovery columns if not present
            cursor.execute("PRAGMA table_info(tenders)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            search_cols = {
                "state": "TEXT",
                "category": "TEXT",
                "tenure_months": "INTEGER",
                "emd_amount_inr": "REAL",
                "location": "TEXT",
                "portal": "TEXT",
            }
            for col_name, col_type in search_cols.items():
                if col_name not in existing_cols:
                    cursor.execute(f"ALTER TABLE tenders ADD COLUMN {col_name} {col_type}")

            conn.commit()

    @staticmethod
    def compute_sha256(data: str) -> str:
        """Returns standard SHA-256 hash."""
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def get_snapshot_by_url(self, source_url: str, org_id: str = "org_default") -> Optional[Dict[str, Any]]:
        """Returns cached snapshot if already ingested for this organization."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM tender_snapshots 
                WHERE source_url = ? AND organization_id = ?
                ORDER BY fetched_at DESC LIMIT 1
            """, (source_url, org_id))
            row = cursor.fetchone()
            if not row:
                return None
            
            # Read extracted json payload from object storage
            extracted_path = Path(row["extracted_json_path"])
            if extracted_path.exists():
                with open(extracted_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        return None

    def get_snapshot_by_tender_number(self, tender_number: str, org_id: str = "org_default") -> Optional[Dict[str, Any]]:
        """Returns cached snapshot by Tender Number / ID if already ingested."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ts.extracted_json_path FROM tenders t
                JOIN tender_snapshots ts ON t.tender_id = ts.tender_id
                WHERE (t.external_id = ? OR t.tender_id = ?) AND t.organization_id = ?
                ORDER BY ts.fetched_at DESC LIMIT 1
            """, (tender_number, tender_number, org_id))
            row = cursor.fetchone()
            if not row:
                return None
            
            extracted_path = Path(row["extracted_json_path"])
            if extracted_path.exists():
                with open(extracted_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        return None

    def save_tender_and_snapshot(
        self,
        org_id: str,
        tender_number: str,
        tender_title: str,
        source_url: str,
        buyer_name: Optional[str],
        submission_deadline: Optional[str],
        estimated_value_inr: Optional[float],
        extracted_data: Dict[str, Any],
        raw_text_payload: str,
        tender_id: Optional[str] = None,
        state: Optional[str] = None,
        category: Optional[str] = None,
        portal: Optional[str] = None,
        tenure_months: Optional[int] = None,
        emd_amount_inr: Optional[float] = None,
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Stores tender metadata and commits an immutable snapshot to tiered storage.
        """
        content_hash = self.compute_sha256(raw_text_payload or json.dumps(extracted_data, sort_keys=True))
        if not tender_id:
            # Check if tender already exists in SQLite by external_id
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT tender_id FROM tenders WHERE external_id = ? LIMIT 1", (tender_number,))
                row = cursor.fetchone()
                if row:
                    tender_id = row[0]
                else:
                    tender_id = f"tnd_{self.compute_sha256(tender_number)[:12]}"

        snapshot_id = f"snp_{content_hash[:16]}"
        now = datetime.now(timezone.utc).isoformat()

        # 1. Save raw and structured payloads to object storage (snapshots folder)
        raw_path = self.snapshots_dir / f"{content_hash}_raw.txt"
        extracted_path = self.snapshots_dir / f"{content_hash}_extracted.json"
        
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(raw_text_payload)
            
        with open(extracted_path, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, indent=2)

        # 2. Commit relational metadata
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Upsert master tender record with search attributes
            cursor.execute("""
                INSERT INTO tenders (
                    tender_id, organization_id, external_id, title, buyer_name,
                    submission_deadline, estimated_value_inr, source_url, created_at, updated_at,
                    state, category, tenure_months, emd_amount_inr, location, portal
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tender_id) DO UPDATE SET
                    title = excluded.title,
                    buyer_name = COALESCE(excluded.buyer_name, tenders.buyer_name),
                    submission_deadline = COALESCE(excluded.submission_deadline, tenders.submission_deadline),
                    estimated_value_inr = COALESCE(excluded.estimated_value_inr, tenders.estimated_value_inr),
                    state = COALESCE(excluded.state, tenders.state),
                    category = COALESCE(excluded.category, tenders.category),
                    tenure_months = COALESCE(excluded.tenure_months, tenders.tenure_months),
                    emd_amount_inr = COALESCE(excluded.emd_amount_inr, tenders.emd_amount_inr),
                    location = COALESCE(excluded.location, tenders.location),
                    portal = COALESCE(excluded.portal, tenders.portal),
                    updated_at = excluded.updated_at
            """, (
                tender_id, org_id, tender_number, tender_title, buyer_name,
                submission_deadline, estimated_value_inr, source_url, now, now,
                state, category, tenure_months, emd_amount_inr, location, portal
            ))
            
            # Append immutable snapshot
            cursor.execute("""
                INSERT OR REPLACE INTO tender_snapshots (
                    snapshot_id, tender_id, organization_id, source_url,
                    content_hash, raw_payload_path, extracted_json_path, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot_id, tender_id, org_id, source_url,
                content_hash, str(raw_path), str(extracted_path), now
            ))
            
            conn.commit()

        return {
            "tender_id": tender_id,
            "snapshot_id": snapshot_id,
            "content_hash": content_hash,
            "raw_payload_path": str(raw_path),
            "extracted_json_path": str(extracted_path),
            "is_cached": False,
        }

    def search_indexed_tenders(
        self,
        query: Optional[str] = None,
        tender_number: Optional[str] = None,
        state: Optional[str] = None,
        category: Optional[str] = None,
        min_value_inr: Optional[float] = None,
        max_value_inr: Optional[float] = None,
        min_tenure_months: Optional[int] = None,
        max_tenure_months: Optional[int] = None,
        buyer_name: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Executes multi-criteria search with full-text keyword matching, tender number lookup, and numeric thresholds.
        """
        clauses = ["1=1"]
        params: List[Any] = []

        if tender_number:
            clauses.append("(external_id LIKE ? OR tender_id LIKE ?)")
            t_kw = f"%{tender_number}%"
            params.extend([t_kw, t_kw])

        if state:
            clauses.append("state = ?")
            params.append(state)

        if category:
            clauses.append("category = ?")
            params.append(category)

        if min_value_inr is not None:
            clauses.append("estimated_value_inr >= ?")
            params.append(min_value_inr)

        if max_value_inr is not None:
            clauses.append("estimated_value_inr <= ?")
            params.append(max_value_inr)

        if min_tenure_months is not None:
            clauses.append("tenure_months >= ?")
            params.append(min_tenure_months)

        if max_tenure_months is not None:
            clauses.append("tenure_months <= ?")
            params.append(max_tenure_months)

        if buyer_name:
            clauses.append("buyer_name LIKE ?")
            params.append(f"%{buyer_name}%")

        if query:
            # Tokenize words in query and match root/stem variations (e.g. roadways -> roadway)
            words = [w.strip() for w in query.split() if len(w.strip()) >= 2]
            if words:
                for w in words:
                    stems = {w.lower()}
                    if w.lower().endswith("ways"):
                        stems.add(w.lower()[:-1])  # roadways -> roadway
                    elif w.lower().endswith("ies") and len(w) > 4:
                        stems.add(w.lower()[:-3] + "y")
                    elif w.lower().endswith("es") and len(w) > 4:
                        stems.add(w.lower()[:-2])
                    elif w.lower().endswith("s") and len(w) > 3:
                        stems.add(w.lower()[:-1])  # roads -> road, bridges -> bridge

                    sub_clauses = []
                    sub_params = []
                    for s in stems:
                        kw = f"%{s}%"
                        sub_clauses.append("(external_id LIKE ? OR tender_id LIKE ? OR title LIKE ? OR buyer_name LIKE ? OR location LIKE ?)")
                        sub_params.extend([kw, kw, kw, kw, kw])
                    clauses.append("(" + " OR ".join(sub_clauses) + ")")
                    params.extend(sub_params)
            else:
                clauses.append("(external_id LIKE ? OR tender_id LIKE ? OR title LIKE ? OR buyer_name LIKE ? OR location LIKE ?)")
                kw = f"%{query}%"
                params.extend([kw, kw, kw, kw, kw])

        where_sql = " AND ".join(clauses)
        sql = f"""
            SELECT tender_id, external_id, title, buyer_name, state, category,
                   estimated_value_inr, emd_amount_inr, tenure_months,
                   submission_deadline, portal, source_url
            FROM tenders
            WHERE {where_sql}
            ORDER BY estimated_value_inr DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        results = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, params)
            for row in cursor.fetchall():
                t_item = {
                    "tender_id": row["tender_id"],
                    "tender_number": row["external_id"],
                    "title": row["title"],
                    "buyer_name": row["buyer_name"],
                    "state": row["state"] or "All India",
                    "category": row["category"] or "Services",
                    "estimated_value_inr": row["estimated_value_inr"],
                    "emd_amount_inr": row["emd_amount_inr"],
                    "tenure_months": row["tenure_months"],
                    "submission_deadline": row["submission_deadline"],
                    "portal": row["portal"] or "Government Portal",
                    "source_url": row["source_url"],
                    "status": "ACTIVE",
                }

                # Attach snapshot skimmed fields if available
                alt_id = f"tnd_{self.compute_sha256(row['external_id'])[:12]}"
                cursor2 = conn.cursor()
                cursor2.execute("""
                    SELECT extracted_json_path, content_hash FROM tender_snapshots
                    WHERE tender_id = ? OR tender_id = ?
                    ORDER BY fetched_at DESC LIMIT 1
                """, (row["tender_id"], alt_id))
                snap_row = cursor2.fetchone()
                if snap_row:
                    t_item["content_hash"] = snap_row["content_hash"]
                    ext_path = Path(snap_row["extracted_json_path"])
                    if ext_path.exists():
                        try:
                            with open(ext_path, "r", encoding="utf-8") as f:
                                snap_data = json.load(f)
                                if isinstance(snap_data, dict):
                                    for k in (
                                        "tender_fee_inr", "processing_fee_inr", "dealing_officer",
                                        "org_hierarchy", "mandatory_documents", "attachments",
                                        "nit_attachment", "boq_attachment", "summary"
                                    ):
                                        if k in snap_data and k not in t_item:
                                            t_item[k] = snap_data[k]
                                    if snap_data.get("estimated_value_inr") is not None and t_item["estimated_value_inr"] is None:
                                        t_item["estimated_value_inr"] = snap_data["estimated_value_inr"]
                                    if snap_data.get("emd_amount_inr") is not None and t_item["emd_amount_inr"] is None:
                                        t_item["emd_amount_inr"] = snap_data["emd_amount_inr"]
                        except Exception:
                            pass

                results.append(t_item)

        return results

    def get_tender(self, identifier: str, mode: str = "skim") -> Optional[Dict[str, Any]]:
        """
        Retrieves a tender by its tender_id or external tender_number.
        Supports exact match and prefix/partial number match.
        Supports two viewing modes:
        - 'skim': Fast high-level overview (financials, buyer, deadline, tenure, status)
        - 'detailed': Complete breakdown including extracted clauses, page citations, and rule pack.
        """
        clean_id = (identifier or "").strip()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM tenders
                WHERE tender_id = ? OR external_id = ? OR external_id LIKE ? OR tender_id LIKE ?
                ORDER BY CASE
                    WHEN external_id = ? THEN 1
                    WHEN tender_id = ? THEN 2
                    WHEN external_id LIKE ? THEN 3
                    ELSE 4
                END
                LIMIT 1
            """, (clean_id, clean_id, f"%{clean_id}%", f"%{clean_id}%", clean_id, clean_id, f"%{clean_id}%"))
            row = cursor.fetchone()
            if not row:
                return None

            cursor.execute("""
                SELECT extracted_json_path, content_hash, fetched_at FROM tender_snapshots
                WHERE tender_id = ? OR tender_id = ?
                ORDER BY fetched_at DESC LIMIT 1
            """, (row["tender_id"], f"tnd_{self.compute_sha256(row['external_id'])[:12]}"))
            snap_row = cursor.fetchone()
            has_snapshot = snap_row is not None

            val = row["estimated_value_inr"]
            tenure = row["tenure_months"]
            state = row["state"] or "All India"
            cat = row["category"] or "Services"

            val_str = f"â‚¹{val:,.2f}" if val else "Not Specified"
            summary_str = f"{val_str} | {tenure}M | {cat} in {state}" if tenure else f"{val_str} | {cat} in {state}"

            tender_dict = {
                "mode": mode,
                "tender_id": row["tender_id"],
                "tender_number": row["external_id"],
                "title": row["title"],
                "buyer_name": row["buyer_name"],
                "state": state,
                "category": cat,
                "estimated_value_inr": val,
                "emd_amount_inr": row["emd_amount_inr"],
                "tenure_months": tenure,
                "submission_deadline": row["submission_deadline"],
                "portal": row["portal"] or "Government Portal",
                "source_url": row["source_url"],
                "status": "ACTIVE",
                "summary": summary_str,
                "has_pdf_document": has_snapshot,
            }

            snap_data = None
            if snap_row:
                extracted_path = Path(snap_row["extracted_json_path"])
                tender_dict["extracted_json_path"] = str(extracted_path)
                if extracted_path.exists():
                    try:
                        with open(extracted_path, "r", encoding="utf-8") as f:
                            snap_data = json.load(f)
                            if isinstance(snap_data, dict):
                                for k in (
                                    "tender_fee_inr", "processing_fee_inr", "dealing_officer",
                                    "org_hierarchy", "mandatory_documents", "attachments",
                                    "nit_attachment", "boq_attachment", "preview_details", "currenttenderid"
                                ):
                                    if k in snap_data and k not in tender_dict:
                                        tender_dict[k] = snap_data[k]
                    except Exception:
                        pass
                tender_dict["content_hash"] = snap_row["content_hash"]
                tender_dict["fetched_at"] = snap_row["fetched_at"]

            if mode == "skim":
                return tender_dict

            # mode == "detailed":
            if snap_row and snap_data:
                tender_dict["extraction"] = snap_data

                # Check if the snapshot contains actual parsed PDF clauses/pages
                ext = tender_dict.get("extraction")
                has_deep_clauses = isinstance(ext, dict) and (
                    bool(ext.get("verbatim_clauses")) or ext.get("total_pages") is not None
                )

                if has_deep_clauses:
                    tender_dict["pdf_status"] = "PARSED"
                    tender_dict["has_pdf_document"] = True
                else:
                    tender_dict["pdf_status"] = "PENDING_INTAKE"
                    tender_dict["has_pdf_document"] = False
                    tender_dict["message"] = (
                        "Full notice PDF has not yet been ingested for this tender. "
                        "Detailed mode will automatically acquire and parse full clauses."
                    )
            else:
                tender_dict["pdf_status"] = "PENDING_INTAKE"
                tender_dict["has_pdf_document"] = False
                tender_dict["message"] = (
                    "Full notice PDF has not yet been ingested for this tender. "
                    "Detailed mode will automatically acquire and parse full clauses."
                )

            return tender_dict


# ==============================================================================
# Unified Single Storage Adapter Interface (put, get, delete, exists)
# ==============================================================================

class StorageBackend:
    """Base interface for swappable storage providers."""
    def put(self, key: str, data: bytes, content_type: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def get(self, key: str) -> Optional[bytes]:
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError


class InMemoryStorageBackend(StorageBackend):
    """Fast in-memory storage backend for unit tests and local isolation."""
    def __init__(self):
        self._store: Dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: Optional[str] = None) -> Dict[str, Any]:
        self._store[key] = bytes(data)
        return {
            "key": key,
            "size": len(data),
            "content_type": content_type or "application/octet-stream",
            "backend": "memory",
        }

    def get(self, key: str) -> Optional[bytes]:
        return self._store.get(key)

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def exists(self, key: str) -> bool:
        return key in self._store


class DiskStorageBackend(StorageBackend):
    """Secure local disk storage backend strictly validating keys against path traversal."""
    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir:
            self.base_dir = Path(base_dir).resolve()
        else:
            self.base_dir = (Path(__file__).resolve().parents[2] / "data" / "vault").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, key: str) -> Path:
        """Guarantees key stays strictly within base_dir and contains no path traversal."""
        clean_key = key.lstrip("/\\")
        target_path = (self.base_dir / clean_key).resolve()
        if not str(target_path).startswith(str(self.base_dir)):
            raise ValueError(f"Path traversal detected in storage key: {key}")
        return target_path

    def put(self, key: str, data: bytes, content_type: Optional[str] = None) -> Dict[str, Any]:
        target_path = self._resolve_safe_path(key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(data)
        return {
            "key": key,
            "size": len(data),
            "content_type": content_type or "application/octet-stream",
            "path": str(target_path),
            "backend": "disk",
        }

    def get(self, key: str) -> Optional[bytes]:
        target_path = self._resolve_safe_path(key)
        if not target_path.exists() or not target_path.is_file():
            return None
        with open(target_path, "rb") as f:
            return f.read()

    def delete(self, key: str) -> bool:
        target_path = self._resolve_safe_path(key)
        if target_path.exists() and target_path.is_file():
            target_path.unlink()
            return True
        return False

    def exists(self, key: str) -> bool:
        target_path = self._resolve_safe_path(key)
        return target_path.exists() and target_path.is_file()


class B2StorageBackend(StorageBackend):
    """Backblaze B2 S3-compatible cloud object storage backend."""
    def __init__(self):
        from backend.services.b2_storage import BackblazeB2Storage
        self.b2 = BackblazeB2Storage()

    def put(self, key: str, data: bytes, content_type: Optional[str] = None) -> Dict[str, Any]:
        return self.b2.upload_bytes(key=key, data=data, content_type=content_type or "application/pdf")

    def get(self, key: str) -> Optional[bytes]:
        return self.b2.download_bytes(key)

    def delete(self, key: str) -> bool:
        return self.b2.delete_file(key)

    def exists(self, key: str) -> bool:
        return self.b2.file_exists(key)


def _init_default_storage() -> StorageBackend:
    backend_type = os.getenv("STORAGE_BACKEND", "").lower()
    if backend_type == "b2" or os.getenv("B2_APPLICATION_KEY_ID") or os.getenv("B2_KEY_ID"):
        try:
            return B2StorageBackend()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to initialize B2StorageBackend: %s. Using DiskStorageBackend.", e)
    return DiskStorageBackend()


# Global storage adapter instance
_active_backend: StorageBackend = _init_default_storage()


def set_storage_backend(backend: StorageBackend):
    """Allows setting an in-memory or alternative backend for testing."""
    global _active_backend
    _active_backend = backend


def get_storage_backend() -> StorageBackend:
    return _active_backend



def put(key: str, data: bytes, content_type: Optional[str] = None) -> Dict[str, Any]:
    """Store data under the specified key."""
    return _active_backend.put(key, data, content_type=content_type)


def get(key: str) -> Optional[bytes]:
    """Retrieve data stored under key."""
    return _active_backend.get(key)


def delete(key: str) -> bool:
    """Delete object stored under key."""
    return _active_backend.delete(key)


def exists(key: str) -> bool:
    """Check if object exists under key."""
    return _active_backend.exists(key)
