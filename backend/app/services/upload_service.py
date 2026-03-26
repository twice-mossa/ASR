from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.schemas.auth import UserProfile
from app.schemas.meeting import (
    ChunkedUploadInitRequest,
    ChunkedUploadInitResponse,
    ChunkedUploadPartResponse,
    MeetingCreateRequest,
    MeetingDetailResponse,
)
from app.services.meeting_service import _create_meeting_record_from_saved_file

_UPLOAD_ROOT_NAME = ".chunk_uploads"
_MANIFEST_NAME = "manifest.json"


def _chunk_upload_root() -> Path:
    path = Path(settings.upload_dir) / _UPLOAD_ROOT_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _session_dir(upload_id: str) -> Path:
    return _chunk_upload_root() / upload_id


def _manifest_path(upload_id: str) -> Path:
    return _session_dir(upload_id) / _MANIFEST_NAME


def _part_path(upload_id: str, part_number: int) -> Path:
    return _session_dir(upload_id) / f"part-{part_number:06d}.bin"


def _write_manifest(session_dir: Path, payload: dict) -> None:
    manifest_path = session_dir / _MANIFEST_NAME
    temp_path = session_dir / f"{_MANIFEST_NAME}.tmp"
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temp_path.replace(manifest_path)


def _load_manifest(upload_id: str) -> dict:
    manifest_path = _manifest_path(upload_id)
    if not manifest_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="上传会话不存在或已过期")

    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="上传会话元数据损坏") from exc


def _require_manifest_owner(manifest: dict, current_user: UserProfile) -> None:
    if int(manifest.get("user_id") or 0) != int(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="上传会话不存在")


def _uploaded_part_numbers(upload_id: str) -> list[int]:
    parts: list[int] = []
    for path in _session_dir(upload_id).glob("part-*.bin"):
        try:
            parts.append(int(path.stem.split("-")[-1]))
        except (ValueError, IndexError):
            continue
    return sorted(set(parts))


def _expected_part_size(manifest: dict, part_number: int) -> int:
    total_chunks = int(manifest["total_chunks"])
    chunk_size = int(manifest["chunk_size"])
    file_size = int(manifest["file_size"])
    if part_number < 1 or part_number > total_chunks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分片序号超出范围")

    if part_number < total_chunks:
        return chunk_size

    consumed = chunk_size * (total_chunks - 1)
    return file_size - consumed if file_size > consumed else chunk_size


def init_chunked_upload(payload: ChunkedUploadInitRequest, current_user: UserProfile) -> ChunkedUploadInitResponse:
    if payload.chunk_size > payload.file_size:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分片大小不能大于文件大小")

    expected_total_chunks = (payload.file_size + payload.chunk_size - 1) // payload.chunk_size
    if payload.total_chunks != expected_total_chunks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分片数量与文件大小不匹配")

    upload_id = uuid.uuid4().hex
    session_dir = _session_dir(upload_id)
    session_dir.mkdir(parents=True, exist_ok=False)
    _write_manifest(
        session_dir,
        {
            "upload_id": upload_id,
            "user_id": int(current_user.id),
            "filename": payload.filename.strip(),
            "duration_label": payload.duration_label or "--:--",
            "file_size": int(payload.file_size),
            "chunk_size": int(payload.chunk_size),
            "total_chunks": int(payload.total_chunks),
            "content_type": payload.content_type or "application/octet-stream",
        },
    )
    return ChunkedUploadInitResponse(
        upload_id=upload_id,
        chunk_size=payload.chunk_size,
        total_chunks=payload.total_chunks,
    )


async def upload_chunk_part(
    upload_id: str,
    part_number: int,
    file: UploadFile,
    current_user: UserProfile,
) -> ChunkedUploadPartResponse:
    manifest = _load_manifest(upload_id)
    _require_manifest_owner(manifest, current_user)

    expected_size = _expected_part_size(manifest, part_number)
    try:
        raw = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="读取分片失败") from exc

    if len(raw) != expected_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"分片大小不正确，期望 {expected_size} 字节，实际 {len(raw)} 字节",
        )

    session_dir = _session_dir(upload_id)
    target_path = _part_path(upload_id, part_number)
    temp_path = session_dir / f"{target_path.name}.tmp-{uuid.uuid4().hex}"
    try:
        temp_path.write_bytes(raw)
        temp_path.replace(target_path)
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="保存分片失败") from exc
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)

    uploaded_parts = len(_uploaded_part_numbers(upload_id))
    return ChunkedUploadPartResponse(
        upload_id=upload_id,
        part_number=part_number,
        uploaded_parts=uploaded_parts,
        total_chunks=int(manifest["total_chunks"]),
    )


def complete_chunked_upload(upload_id: str, current_user: UserProfile) -> MeetingDetailResponse:
    manifest = _load_manifest(upload_id)
    _require_manifest_owner(manifest, current_user)

    session_dir = _session_dir(upload_id)
    total_chunks = int(manifest["total_chunks"])
    expected_parts = list(range(1, total_chunks + 1))
    actual_parts = _uploaded_part_numbers(upload_id)
    if actual_parts != expected_parts:
        missing_parts = [part for part in expected_parts if part not in actual_parts]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"分片未上传完整，缺少分片: {', '.join(str(part) for part in missing_parts[:8])}",
        )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(str(manifest["filename"])).suffix.lower()
    stored_filename = f"{uuid.uuid4().hex}{suffix}"
    final_path = upload_dir / stored_filename
    merged_bytes = 0

    try:
        with final_path.open("wb") as target:
            for part_number in expected_parts:
                part_path = _part_path(upload_id, part_number)
                expected_size = _expected_part_size(manifest, part_number)
                actual_size = part_path.stat().st_size if part_path.exists() else -1
                if actual_size != expected_size:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"分片 {part_number} 大小校验失败，期望 {expected_size} 字节，实际 {actual_size} 字节",
                    )

                with part_path.open("rb") as source:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                merged_bytes += actual_size
    except HTTPException:
        final_path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        final_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="合并分片失败") from exc

    if merged_bytes != int(manifest["file_size"]):
        final_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="合并后的文件大小校验失败")

    try:
        return _create_meeting_record_from_saved_file(
            payload=MeetingCreateRequest(
                filename=str(manifest["filename"]),
                duration_label=str(manifest.get("duration_label") or "--:--"),
            ),
            filename=str(manifest["filename"]),
            stored_filename=stored_filename,
            audio_path=final_path,
            content_type=str(manifest.get("content_type") or "application/octet-stream"),
            current_user=current_user,
        )
    finally:
        shutil.rmtree(session_dir, ignore_errors=True)


def cleanup_chunked_upload(upload_id: str) -> None:
    shutil.rmtree(_session_dir(upload_id), ignore_errors=True)
