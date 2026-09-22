"""
scripts/engine/io.py
====================
Robuste, idempotente Datei-I/O mit atomaren Schreibvorgängen,
Inhalts-Gleichheitsprüfung und resilienten Fallbacks für Sandboxes und Container.

Architekturmerkmale:
1. Idempotenz durch Content-Hashing/Equality-Check vor Schreibzugriff
   (Verhindert unmotivierte Inode- und mtime-Änderungen und Git-Diff-Jitter).
2. Atomarität durch Staging über temporäre Dateien und atomare Dateisystem-Renames.
3. Resilienz durch dreistufige Fallback-Kaskade bei restriktiven Sandbox-Mounts:
   - Stufe 1: `mkstemp` im Zielverzeichnis (atomar via `os.replace`).
   - Stufe 2: `mkstemp` in `/tmp` mit dateisystemübergreifendem Transfer (`shutil.move`).
   - Stufe 3: Direkter Inplace-Write bei blockierten Tempfile-Rechten.
"""

import os
import shutil
import tempfile


class FileUtils:
    """
    Werkzeuge für verlässliche, atomare und idempotente Dateisystem-Operationen.
    """

    @staticmethod
    def atomic_write_if_changed(filepath: str, content: str, encoding: str = "utf-8") -> bool:
        """
        Schreibt den übergebenen Inhalt nur dann auf die Festplatte, wenn er sich
        vom gegenwärtigen Dateiinhalt unterscheidet.

        Parameter:
            filepath: Zielpfad der zu schreibenden Datei.
            content: Neuer Dateiinhalt als String.
            encoding: Textkodierung (Standard: 'utf-8').

        Rückgabe:
            True: Datei wurde neu angelegt oder geändert.
            False: Datei existiert bereits mit identischem Inhalt; kein Schreibzugriff.
        """
        filepath = os.path.abspath(filepath)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    if f.read() == content:
                        return False  # Inhalt identisch -> Kein Schreibzugriff nötig
            except Exception:
                pass

        out_dir = os.path.dirname(filepath)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        # 1. Stufe: Tempfile im Zielverzeichnis (echter POSIX-atomarer rename via os.replace)
        try:
            temp_fd, temp_path = tempfile.mkstemp(dir=out_dir, prefix="sync_tmp_", suffix=".tmp")
            with os.fdopen(temp_fd, "w", encoding=encoding) as f:
                f.write(content)
            os.replace(temp_path, filepath)
            return True
        except OSError:
            # 2. Stufe: Systemweites Temp-Verzeichnis (falls Workspace z.B. sandbox-isoliert ist)
            try:
                temp_fd, temp_path = tempfile.mkstemp(dir=tempfile.gettempdir(), prefix="sync_tmp_", suffix=".tmp")
                with os.fdopen(temp_fd, "w", encoding=encoding) as f:
                    f.write(content)
                shutil.move(temp_path, filepath)
                return True
            except Exception:
                # 3. Stufe: Direkter Inplace-Write als Notfall-Fallback
                with open(filepath, "w", encoding=encoding) as f:
                    f.write(content)
                return True

    @staticmethod
    def read_file(filepath: str, encoding: str = "utf-8") -> str:
        """
        Liest eine Textdatei standardkonform ein.

        Parameter:
            filepath: Pfad zur einzulesenden Datei.
            encoding: Textkodierung (Standard: 'utf-8').

        Rückgabe:
            Vollständiger Dateiinhalt als String.
        """
        with open(filepath, "r", encoding=encoding) as f:
            return f.read()

    @staticmethod
    def ensure_dir(dirpath: str) -> None:
        """
        Erstellt ein Verzeichnis rekursiv, falls es noch nicht existiert.

        Parameter:
            dirpath: Zu erstellender Verzeichnispfad.
        """
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
