"""附件存储：/v1/files 上传与内联附件落盘。"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".txt", ".md", ".docx"}
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_ATTACHMENTS_PER_REQUEST = 5

MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


@dataclass
class StoredFile:
    id: str
    filename: str
    path: Path
    size: int
    created_at: float
    purpose: str

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "object": "file",
            "bytes": self.size,
            "created_at": int(self.created_at),
            "filename": self.filename,
            "purpose": self.purpose,
        }


class FileStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.tmp_dir = base_dir / "tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = base_dir / "index.json"
        self._index: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self._index_path.exists():
            try:
                self._index = json.loads(self._index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._index = {}

    def _persist(self) -> None:
        payload = json.dumps(self._index, ensure_ascii=False, indent=2)
        tmp = self._index_path.with_suffix(".tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(self._index_path)

    def _record(self, file_id: str, filename: str, path: Path, size: int, purpose: str) -> StoredFile:
        stored = StoredFile(
            id=file_id,
            filename=filename,
            path=path,
            size=size,
            created_at=time.time(),
            purpose=purpose,
        )
        self._index[file_id] = {
            "filename": filename,
            "path": str(path.relative_to(self.base_dir)),
            "size": size,
            "created_at": stored.created_at,
            "purpose": purpose,
        }
        self._persist()
        return stored

    @staticmethod
    def validate_extension(filename: str) -> str:
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            allowed = "、".join(sorted(ALLOWED_EXTENSIONS))
            raise ValueError(f"不支持的文件类型 {ext or '(无扩展名)'}；支持：{allowed}")
        return ext

    def save_bytes(self, data: bytes, filename: str, kind: str = "file") -> StoredFile:
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("文件超过 25MB 限制")
        ext = self.validate_extension(filename)
        file_id = "file-" + uuid.uuid4().hex[:20]
        target_dir = self.base_dir if kind == "file" else self.tmp_dir
        target = target_dir / f"{file_id}{ext}"
        target.write_bytes(data)
        if kind != "file":
            return StoredFile(
                id=file_id,
                filename=filename,
                path=target,
                size=len(data),
                created_at=time.time(),
                purpose="inline",
            )
        return self._record(file_id, filename, target, len(data), "assistants")

    def add_from_path(self, source: Path, filename: str, purpose: str = "assistants") -> StoredFile:
        self.validate_extension(filename)
        file_id = "file-" + uuid.uuid4().hex[:20]
        target = self.base_dir / f"{file_id}{Path(filename).suffix.lower()}"
        shutil.copyfile(source, target)
        return self._record(file_id, filename, target, target.stat().st_size, purpose)

    def get(self, file_id: str) -> StoredFile | None:
        record = self._index.get(file_id)
        if not record:
            return None
        path = self.base_dir / record["path"]
        if not path.exists():
            return None
        return StoredFile(
            id=file_id,
            filename=record["filename"],
            path=path,
            size=record.get("size", path.stat().st_size),
            created_at=record.get("created_at", 0.0),
            purpose=record.get("purpose", "assistants"),
        )

    def list(self) -> list[StoredFile]:
        files = [self.get(file_id) for file_id in list(self._index.keys())]
        return [item for item in files if item is not None]

    def delete(self, file_id: str) -> bool:
        record = self._index.pop(file_id, None)
        if not record:
            return False
        path = self.base_dir / record["path"]
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
        self._persist()
        return True

    def cleanup_tmp(self, max_age_seconds: float = 48 * 3600) -> int:
        """清理过期的内联附件临时文件与上传中转目录。"""
        removed = 0
        now = time.time()
        try:
            entries = list(self.tmp_dir.iterdir())
        except OSError:
            return 0
        for entry in entries:
            try:
                if now - entry.stat().st_mtime <= max_age_seconds:
                    continue
                if entry.is_dir():
                    shutil.rmtree(entry, ignore_errors=True)
                    removed += 1
                elif entry.is_file():
                    entry.unlink()
                    removed += 1
            except OSError:
                continue
        return removed
