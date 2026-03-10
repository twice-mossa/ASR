from fastapi import UploadFile

from app.schemas.meeting import TranscriptResponse, TranscriptSegment


async def transcribe_audio(file: UploadFile) -> TranscriptResponse:
    content = await file.read()
    size_hint = len(content)
    preview = "这是一个示例转写结果，后续替换为 faster-whisper 实际识别输出。"

    return TranscriptResponse(
        filename=file.filename or "unknown.wav",
        language="zh",
        text=f"{preview} 当前文件大小约 {size_hint} 字节。",
        segments=[
            TranscriptSegment(start=0.0, end=6.0, text="大家好，现在开始今天的项目会议。"),
            TranscriptSegment(start=6.0, end=14.0, text="本次讨论重点是语音识别、会议纪要和搜索回放功能。"),
        ],
    )
