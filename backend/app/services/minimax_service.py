from app.schemas.meeting import MeetingSummaryResponse, TranscriptResponse


async def build_mock_summary(payload: TranscriptResponse) -> MeetingSummaryResponse:
    base_summary = "本次会议围绕智能会议助手的核心功能展开，明确了语音转写、纪要生成和关键词检索为当前优先目标。"

    return MeetingSummaryResponse(
        summary=base_summary,
        keywords=["会议助手", "语音识别", "纪要生成", "关键词搜索"],
        action_items=[
            "完成 faster-whisper 模块接入",
            "接入 MiniMax API 生成摘要",
            "补充前端上传与结果展示页面",
        ],
    )
