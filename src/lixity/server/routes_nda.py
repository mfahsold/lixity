"""Project-owned NDA management routes.

The store, templates and exports resolve against the active project root, so
switching projects switches the provider. A project without NDA capability is
answered with 404 rather than an empty list.
"""

from __future__ import annotations

from typing import Any

from ._base import ResponseMixin


class NdaRoutesMixin(ResponseMixin):
    """Handlers for NDA unlock/list/add/update/export/delete."""

    def _handle_nda(self, action: str, payload: dict[str, Any]) -> None:
        if self.nda_provider is None or not self.nda_provider.is_available():
            self._json(
                {"ok": False, "message": "NDA management is not enabled for this project"}, 404
            )
            return

        if action == "nda-list":
            try:
                records = self.nda_provider.list_records()
                self._json({"ok": True, "records": records})
            except PermissionError as exc:
                self._json({"ok": False, "message": str(exc), "locked": True}, 403)
            except (OSError, RuntimeError, ValueError, KeyError):
                self._json({"ok": False, "message": "Failed to read NDA store"}, 500)
            return

        if action == "nda-unlock":
            passphrase = str(payload.get("passphrase") or "")
            ok = self.nda_provider.unlock(passphrase)
            if ok:
                try:
                    records = self.nda_provider.list_records()
                except (OSError, RuntimeError, PermissionError, ValueError, KeyError):
                    records = []
                self._json({"ok": True, "message": "NDA store unlocked", "records": records})
            else:
                self._json({"ok": False, "message": "Invalid passphrase"}, 401)
            return

        if action == "nda-add":
            name = str(payload.get("name") or "").strip()
            contact = str(payload.get("contact") or "").strip()
            notes = str(payload.get("notes") or "").strip()
            if not name:
                self._json({"ok": False, "message": "Recipient name is required"}, 400)
                return
            try:
                record = self.nda_provider.add_record(name, contact, notes)
                self._json(
                    {
                        "ok": True,
                        "message": f"NDA created for {name}",
                        "id": record["id"],
                        "record": record,
                    }
                )
            except PermissionError as exc:
                self._json({"ok": False, "message": str(exc), "locked": True}, 403)
            except ValueError as exc:
                self._json({"ok": False, "message": str(exc)}, 400)
            except (OSError, RuntimeError, KeyError):
                self._json({"ok": False, "message": "Failed to add NDA record"}, 500)
            return

        if action == "nda-update":
            rec_id = str(payload.get("id") or "").strip()
            status = str(payload.get("status") or "").strip()
            if not rec_id or not status:
                self._json({"ok": False, "message": "Record ID and status are required"}, 400)
                return
            try:
                record = self.nda_provider.update_status(rec_id, status)
                self._json(
                    {"ok": True, "message": f"Status updated to '{status}'", "record": record}
                )
            except KeyError as exc:
                self._json({"ok": False, "message": str(exc)}, 404)
            except ValueError as exc:
                self._json({"ok": False, "message": str(exc)}, 400)
            except PermissionError as exc:
                self._json({"ok": False, "message": str(exc), "locked": True}, 403)
            except (OSError, RuntimeError):
                self._json({"ok": False, "message": "Failed to update NDA record"}, 500)
            return

        if action == "nda-export":
            rec_id = str(payload.get("id") or "").strip()
            if not rec_id:
                self._json({"ok": False, "message": "Record ID is required"}, 400)
                return
            try:
                pdf = self.nda_provider.export_pdf(rec_id)
                self._json({"ok": True, "message": f"NDA exported as {pdf}", "pdf": pdf})
            except KeyError as exc:
                self._json({"ok": False, "message": str(exc)}, 404)
            except PermissionError as exc:
                self._json({"ok": False, "message": str(exc), "locked": True}, 403)
            except (OSError, RuntimeError, ValueError):
                self._json({"ok": False, "message": "Failed to export NDA"}, 500)
            return

        if action == "nda-delete":
            rec_id = str(payload.get("id") or "").strip()
            if not rec_id:
                self._json({"ok": False, "message": "Record ID is required"}, 400)
                return
            try:
                ok = self.nda_provider.delete_record(rec_id)
                if ok:
                    self._json({"ok": True, "message": "NDA record deleted"})
                else:
                    self._json({"ok": False, "message": f"NDA record not found: {rec_id}"}, 404)
            except PermissionError as exc:
                self._json({"ok": False, "message": str(exc), "locked": True}, 403)
            except (OSError, RuntimeError, KeyError, ValueError):
                self._json({"ok": False, "message": "Failed to delete NDA record"}, 500)
            return

        self._json({"ok": False, "message": f"Unknown NDA action: {action}"}, 400)

