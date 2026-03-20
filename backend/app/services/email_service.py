from __future__ import annotations

import html
import json
import smtplib
from email.message import EmailMessage

from fastapi import HTTPException, status
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Meeting, MeetingSummary, MeetingSummaryEmailDelivery
from app.schemas.auth import UserProfile
from app.schemas.meeting import MeetingSummaryEmailSendResponse


def email_delivery_enabled() -> bool:
    return bool(
        settings.smtp_host
        and settings.smtp_port
        and settings.smtp_username
        and settings.smtp_password
        and settings.smtp_from_email
    )


def _get_session():
    return SessionLocal()


def _parse_json_list(raw: str) -> list[str]:
    try:
        values = json.loads(raw or "[]")
    except json.JSONDecodeError:
        values = []
    return [str(item) for item in values if str(item).strip()]


def _build_subject(meeting: Meeting) -> str:
    meeting_title = str(meeting.title or meeting.filename or f"会议 {meeting.id}").strip()
    return f"【会议纪要】{meeting_title}"


def _build_html_body(
    *,
    meeting: Meeting,
    summary: MeetingSummary,
    keywords: list[str],
    todos: list[str],
) -> str:
    meeting_title = html.escape(str(meeting.title or meeting.filename or f"会议 {meeting.id}"))
    filename = html.escape(str(meeting.filename or ""))
    summary_text = html.escape(str(summary.summary or "暂无摘要内容。")).replace("\n", "<br />")
    generated_at = summary.updated_at.isoformat() if summary.updated_at else (summary.created_at.isoformat() if summary.created_at else "")
    keyword_items = "".join(f"<li>{html.escape(item)}</li>" for item in keywords) or "<li>暂无关键词</li>"
    todo_items = "".join(f"<li>{html.escape(item)}</li>" for item in todos) or "<li>暂无待办事项</li>"

    return f"""
<!doctype html>
<html lang="zh-CN">
  <body style="margin:0;padding:24px;background:#f5f7fb;color:#0f172a;font-family:'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;">
    <div style="max-width:720px;margin:0 auto;background:#ffffff;border:1px solid #d9e2f0;border-radius:18px;overflow:hidden;">
      <div style="padding:20px 24px;background:linear-gradient(135deg,#12306b,#2449b8);color:#ffffff;">
        <div style="font-size:12px;letter-spacing:0.14em;text-transform:uppercase;opacity:0.82;">Meeting Notes</div>
        <h1 style="margin:10px 0 0;font-size:24px;line-height:1.2;">{meeting_title}</h1>
      </div>
      <div style="padding:24px;">
        <p style="margin:0 0 6px;color:#5b6780;font-size:13px;">音频文件：{filename or '未命名会议'}</p>
        <p style="margin:0 0 24px;color:#5b6780;font-size:13px;">生成时间：{html.escape(generated_at or '未知')}</p>

        <section style="margin-bottom:24px;">
          <h2 style="margin:0 0 10px;font-size:18px;color:#0f172a;">会议摘要</h2>
          <div style="color:#1f2937;line-height:1.8;font-size:14px;">{summary_text}</div>
        </section>

        <section style="margin-bottom:24px;">
          <h2 style="margin:0 0 10px;font-size:18px;color:#0f172a;">关键词</h2>
          <ul style="margin:0;padding-left:20px;color:#1f2937;line-height:1.8;font-size:14px;">{keyword_items}</ul>
        </section>

        <section>
          <h2 style="margin:0 0 10px;font-size:18px;color:#0f172a;">待办事项</h2>
          <ul style="margin:0;padding-left:20px;color:#1f2937;line-height:1.8;font-size:14px;">{todo_items}</ul>
        </section>
      </div>
      <div style="padding:16px 24px;border-top:1px solid #e5ebf5;color:#667085;font-size:12px;">
        此邮件由 Audio Memo 工作台自动整理发送。
      </div>
    </div>
  </body>
</html>
""".strip()


def _build_plain_text(
    *,
    meeting: Meeting,
    summary: MeetingSummary,
    keywords: list[str],
    todos: list[str],
) -> str:
    title = str(meeting.title or meeting.filename or f"会议 {meeting.id}")
    generated_at = summary.updated_at.isoformat() if summary.updated_at else (summary.created_at.isoformat() if summary.created_at else "")
    keyword_lines = "\n".join(f"- {item}" for item in keywords) or "- 暂无关键词"
    todo_lines = "\n".join(f"- {item}" for item in todos) or "- 暂无待办事项"

    return "\n".join(
        [
            title,
            "",
            f"音频文件：{meeting.filename or '未命名会议'}",
            f"生成时间：{generated_at or '未知'}",
            "",
            "会议摘要",
            str(summary.summary or "暂无摘要内容。"),
            "",
            "关键词",
            keyword_lines,
            "",
            "待办事项",
            todo_lines,
            "",
            "此邮件由 Audio Memo 工作台自动整理发送。",
        ]
    )


def _record_delivery(
    db,
    *,
    meeting_id: int,
    recipient_email: str,
    delivery_type: str,
    subject: str,
    status_value: str,
    error_message: str = "",
) -> MeetingSummaryEmailDelivery:
    record = MeetingSummaryEmailDelivery(
        meeting_id=meeting_id,
        recipient_email=recipient_email,
        delivery_type=delivery_type,
        status=status_value,
        subject=subject,
        error_message=error_message,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _send_message(message: EmailMessage) -> None:
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.ehlo()
        if settings.smtp_use_tls:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def send_summary_email_for_meeting(
    meeting_id: int,
    current_user: UserProfile,
    *,
    delivery_type: str = "manual",
    raise_on_error: bool = True,
) -> MeetingSummaryEmailSendResponse | None:
    with _get_session() as db:
        meeting = db.execute(
            select(Meeting).where(Meeting.id == meeting_id, Meeting.user_id == current_user.id)
        ).scalar_one_or_none()
        if meeting is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会议记录不存在")

        summary = db.execute(
            select(MeetingSummary).where(MeetingSummary.meeting_id == meeting.id)
        ).scalar_one_or_none()
        if summary is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先生成会议摘要")

        recipient_email = current_user.email
        subject = _build_subject(meeting)
        if not email_delivery_enabled():
            _record_delivery(
                db,
                meeting_id=meeting.id,
                recipient_email=recipient_email,
                delivery_type=delivery_type,
                subject=subject,
                status_value="failed",
                error_message="SMTP 邮件发送未配置",
            )
            if raise_on_error:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="邮件发送未配置")
            return None

        keywords = _parse_json_list(summary.keywords_json)
        todos = _parse_json_list(summary.todos_json)
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = (
            f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
            if settings.smtp_from_name
            else settings.smtp_from_email
        )
        message["To"] = recipient_email
        message.set_content(
            _build_plain_text(
                meeting=meeting,
                summary=summary,
                keywords=keywords,
                todos=todos,
            )
        )
        message.add_alternative(
            _build_html_body(
                meeting=meeting,
                summary=summary,
                keywords=keywords,
                todos=todos,
            ),
            subtype="html",
        )

        try:
            _send_message(message)
        except Exception as exc:
            _record_delivery(
                db,
                meeting_id=meeting.id,
                recipient_email=recipient_email,
                delivery_type=delivery_type,
                subject=subject,
                status_value="failed",
                error_message=str(exc),
            )
            if raise_on_error:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="邮件发送失败，请稍后重试") from exc
            return None

        delivery = _record_delivery(
            db,
            meeting_id=meeting.id,
            recipient_email=recipient_email,
            delivery_type=delivery_type,
            subject=subject,
            status_value="sent",
        )
        return MeetingSummaryEmailSendResponse(
            message="会议纪要已发送到邮箱",
            recipient_email=recipient_email,
            status="sent",
            sent_at=delivery.created_at.isoformat() if delivery.created_at else None,
        )


def maybe_auto_send_summary_email(meeting_id: int, current_user: UserProfile) -> None:
    if not settings.summary_email_auto_send:
        return
    send_summary_email_for_meeting(meeting_id, current_user, delivery_type="auto", raise_on_error=False)
