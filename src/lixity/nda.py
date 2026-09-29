"""Project-owned NDA management provider and storage.

Provides isolated encrypted or structured NDA record storage and document export
for projects that opt into the NDA capability. Data, recipient records, and keys
remain strictly project-owned within <project>/nda/. Recipient names, contacts,
and passphrases are never emitted to logs.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .config import load_project_config
from .status import NdaStatus


class NdaProvider(Protocol):
    """Protocol for project-specific NDA providers."""

    def is_available(self) -> bool: ...
    def is_locked(self) -> bool: ...
    def unlock(self, passphrase: str) -> bool: ...
    def list_records(self) -> list[dict[str, Any]]: ...
    def add_record(self, name: str, contact: str = "", notes: str = "") -> dict[str, Any]: ...
    def update_status(self, record_id: str, status: str) -> dict[str, Any]: ...
    def export_pdf(self, record_id: str) -> str: ...
    def delete_record(self, record_id: str) -> bool: ...


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive 32-byte encryption key from passphrase and salt using PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, iterations=100_000, dklen=32
    )


def _encrypt_bytes(key: bytes, plaintext: bytes) -> bytes:
    """Encrypt plaintext with AES-GCM or authenticated keystream fallback."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        return b"gcm:" + nonce + ciphertext
    except ImportError:
        # Standard library authenticated keystream fallback
        nonce = secrets.token_bytes(16)
        keystream = hashlib.sha256(key + nonce).digest()
        while len(keystream) < len(plaintext):
            keystream += hashlib.sha256(key + keystream[-32:]).digest()
        xor_bytes = bytes(
            p ^ k for p, k in zip(plaintext, keystream[: len(plaintext)], strict=True)
        )
        tag = hmac.new(key, nonce + xor_bytes, hashlib.sha256).digest()
        return b"std:" + nonce + tag + xor_bytes


def _decrypt_bytes(key: bytes, payload: bytes) -> bytes:
    """Decrypt payload produced by _encrypt_bytes."""
    if payload.startswith(b"gcm:"):
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        body = payload[4:]
        nonce, ciphertext = body[:12], body[12:]
        aesgcm = AESGCM(key)
        try:
            return aesgcm.decrypt(nonce, ciphertext, None)
        except InvalidTag as exc:
            raise ValueError("Authentication tag mismatch: incorrect passphrase or corrupted data") from exc
    elif payload.startswith(b"std:"):
        body = payload[4:]
        nonce = body[:16]
        tag = body[16:48]
        xor_bytes = body[48:]
        expected_tag = hmac.new(key, nonce + xor_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError("Authentication tag mismatch: incorrect passphrase or corrupted data")
        keystream = hashlib.sha256(key + nonce).digest()
        while len(keystream) < len(xor_bytes):
            keystream += hashlib.sha256(key + keystream[-32:]).digest()
        return bytes(c ^ k for c, k in zip(xor_bytes, keystream[: len(xor_bytes)], strict=True))
    else:
        raise ValueError("Unknown encrypted envelope format")


class ProjectNdaProvider:
    """Default project-isolated NDA provider storing encrypted or plain records in <project>/nda/."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.nda_dir = self.project_root / "nda"
        self.enc_file = self.nda_dir / "nda_store.enc"
        self.json_file = self.nda_dir / "records.json"
        self._key: bytes | None = None
        self._salt: bytes | None = None
        self._records: list[dict[str, Any]] | None = None
        self._locked = False
        self._init_state()

    def _init_state(self) -> None:
        self.nda_dir.mkdir(parents=True, exist_ok=True)
        if self.enc_file.is_file():
            self._locked = True
            self._records = None
        elif self.json_file.is_file():
            self._locked = False
            try:
                data = json.loads(self.json_file.read_text(encoding="utf-8"))
                self._records = data if isinstance(data, list) else []
            except (OSError, ValueError):
                self._records = []
        else:
            self._locked = False
            self._records = []

    def is_available(self) -> bool:
        return True

    def is_locked(self) -> bool:
        return self._locked

    def unlock(self, passphrase: str) -> bool:
        clean_pass = passphrase.strip()
        if not clean_pass:
            if not self.enc_file.is_file():
                self._locked = False
                return True
            return False

        if self.enc_file.is_file():
            try:
                raw = json.loads(self.enc_file.read_text(encoding="utf-8"))
                salt = base64.b64decode(raw["salt"])
                payload = base64.b64decode(raw["data"])
                key = _derive_key(clean_pass, salt)
                decrypted = _decrypt_bytes(key, payload)
                records = json.loads(decrypted.decode("utf-8"))
                if not isinstance(records, list):
                    return False
                self._salt = salt
                self._key = key
                self._records = records
                self._locked = False
                return True
            except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError):
                return False
        else:
            # First-time passphrase setting for unencrypted store
            salt = secrets.token_bytes(16)
            self._salt = salt
            self._key = _derive_key(clean_pass, salt)
            self._locked = False
            if self._records is None:
                self._records = []
            self._save()
            return True

    def _save(self) -> None:
        if self._records is None or self._locked:
            return
        records_json = json.dumps(self._records, ensure_ascii=False, indent=2).encode("utf-8")
        if self._key is not None or self.enc_file.is_file():
            if self._key is None or self._salt is None:
                raise RuntimeError("Cannot save locked encrypted store")
            payload = _encrypt_bytes(self._key, records_json)
            envelope = {
                "version": 1,
                "salt": base64.b64encode(self._salt).decode("ascii"),
                "data": base64.b64encode(payload).decode("ascii"),
            }
            tmp = self.nda_dir / ".store.enc.tmp"
            tmp.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
            os.replace(tmp, self.enc_file)
            if self.json_file.is_file():
                with contextlib_suppress():
                    self.json_file.unlink()
        else:
            tmp = self.nda_dir / ".records.json.tmp"
            tmp.write_text(records_json.decode("utf-8"), encoding="utf-8")
            os.replace(tmp, self.json_file)

    def list_records(self) -> list[dict[str, Any]]:
        if self._locked or self._records is None:
            raise PermissionError("NDA store is locked; passphrase unlock required")
        return [dict(rec) for rec in self._records]

    def add_record(self, name: str, contact: str = "", notes: str = "") -> dict[str, Any]:
        if self._locked or self._records is None:
            raise PermissionError("NDA store is locked; passphrase unlock required")
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Recipient name is required")
        clean_contact = contact.strip()
        clean_notes = notes.strip()

        next_id = 1
        for rec in self._records:
            rec_id_val = rec.get("id")
            if isinstance(rec_id_val, (int, str)) and str(rec_id_val).isdigit():
                next_id = max(next_id, int(rec_id_val) + 1)

        record: dict[str, Any] = {
            "id": str(next_id),
            "name": clean_name,
            "contact": clean_contact or "–",
            "notes": clean_notes,
            "status": NdaStatus.DRAFT.value,
            "pdf": f"nda_{next_id}.pdf",
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self._records.append(record)
        self._save()
        self._generate_pdf(record)
        return record

    def update_status(self, record_id: str, status: str) -> dict[str, Any]:
        if self._locked or self._records is None:
            raise PermissionError("NDA store is locked; passphrase unlock required")
        valid_statuses = NdaStatus.all_values()
        if status not in valid_statuses:
            raise ValueError(f"Invalid NDA status: '{status}'. Valid: {', '.join(valid_statuses)}")

        rec = next((r for r in self._records if str(r.get("id")) == str(record_id)), None)
        if rec is None:
            raise KeyError(f"NDA record not found: {record_id}")
        rec["status"] = status
        rec["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._save()
        return dict(rec)

    def export_pdf(self, record_id: str) -> str:
        if self._locked or self._records is None:
            raise PermissionError("NDA store is locked; passphrase unlock required")
        rec = next((r for r in self._records if str(r.get("id")) == str(record_id)), None)
        if rec is None:
            raise KeyError(f"NDA record not found: {record_id}")
        return self._generate_pdf(rec)

    def delete_record(self, record_id: str) -> bool:
        if self._locked or self._records is None:
            raise PermissionError("NDA store is locked; passphrase unlock required")
        initial_len = len(self._records)
        self._records = [r for r in self._records if str(r.get("id")) != str(record_id)]
        if len(self._records) < initial_len:
            self._save()
            return True
        return False

    def _generate_pdf(self, record: dict[str, Any]) -> str:
        """Generate PDF or template document using project script if available, or structured fallback."""
        export_script = self.project_root / "scripts" / "export_nda.py"
        pdf_name = f"nda_{record['id']}.pdf"
        target_path = self.nda_dir / pdf_name

        if export_script.is_file():
            import subprocess
            import sys

            cmd = [
                sys.executable,
                str(export_script),
                "--id",
                str(record["id"]),
                "--output",
                str(target_path),
            ]
            try:
                subprocess.run(  # noqa: S603
                    cmd, cwd=str(self.project_root), check=True, capture_output=True, timeout=10
                )
                return pdf_name
            except (subprocess.SubprocessError, OSError):
                pass

        # Built-in synthetic PDF / text receipt generator
        header = f"%PDF-1.4\n% Lixity NDA Agreement Document\n% Recipient ID: {record['id']}\n"
        body = (
            "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R >>\nendobj\n"
            "4 0 obj\n<< /Length 100 >>\nstream\nBT /F1 12 Tf 50 800 Td (Non-Disclosure Agreement) Tj ET\nendstream\nendobj\n"
            "xref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000059 00000 n \n0000000116 00000 n \n0000000196 00000 n \n"
            "trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n350\n%%EOF\n"
        )
        target_path.write_bytes((header + body).encode("utf-8"))
        return pdf_name


def contextlib_suppress() -> Any:
    import contextlib

    return contextlib.suppress(OSError)


def has_nda_support(project_root: str | Path | None) -> bool:
    """Return True if the project explicitly enables or contains NDA capability."""
    if not project_root:
        return False
    root = Path(project_root).resolve()
    if not root.is_dir():
        return False
    if (root / "nda").is_dir():
        return True
    if (root / "scripts" / "nda_store.py").is_file() or (
        root / "scripts" / "export_nda.py"
    ).is_file():
        return True
    if (root / "nda_provider.py").is_file():
        return True
    config = load_project_config(root)
    nda_cfg = config.get("nda")
    if isinstance(nda_cfg, dict) and nda_cfg.get("enabled"):
        return True
    if nda_cfg is True:
        return True
    capabilities = config.get("capabilities")
    return bool(isinstance(capabilities, dict) and capabilities.get("nda"))


def get_project_nda_provider(project_root: str | Path | None) -> NdaProvider | None:
    """Return an active NdaProvider instance if project has NDA capability, else None."""
    if not project_root or not has_nda_support(project_root):
        return None
    root = Path(project_root).resolve()
    # Check for custom adapter module
    custom_adapter = root / "nda_provider.py"
    if custom_adapter.is_file():
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("project_nda_provider", custom_adapter)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                provider_cls = getattr(mod, "Provider", getattr(mod, "NdaProvider", None))
                if provider_cls:
                    return provider_cls(root)  # type: ignore[no-any-return]
        except (ImportError, AttributeError, OSError, TypeError):
            # Fall back to standard ProjectNdaProvider if custom adapter fails to load
            pass
    return ProjectNdaProvider(root)
