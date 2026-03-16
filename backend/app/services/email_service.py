from __future__ import annotations

import html
import smtplib
from email.message import EmailMessage

from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.auth import UserProfile
from app.schemas.meeting import EmailDeliveryRequest, EmailDeliveryResponse


def _require_smtp_settings() -> None:
    required = [
        settings.smtp_host,
        settings.smtp_from_email,
    ]
    if not all(required):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="邮件服务未配置。请先在后端 .env 中配置 SMTP 参数。",
        )


def _build_email_content(payload: EmailDeliveryRequest, user: UserProfile) -> tuple[str, str]:
    subject = f"会议纪要 - {payload.summary_mode} - {user.username}"
    keywords = "、".join(payload.keywords) if payload.keywords else "无"
    todos = "\n".join(f"- {item}" for item in payload.todos) if payload.todos else "- 无"
    transcript_preview = (payload.transcript_text or "").strip()
    if len(transcript_preview) > 1500:
        transcript_preview = transcript_preview[:1500] + "..."

    text_body = (
        f"你好，{user.username}：\n\n"
        f"以下是系统为你生成的会议纪要。\n\n"
        f"Agent: {payload.agent_name or 'meeting-secretary-agent'}\n"
        f"模式: {payload.summary_mode}\n"
        f"场景: {payload.scene}\n\n"
        f"会议摘要:\n{payload.summary}\n\n"
        f"关键词:\n{keywords}\n\n"
        f"待办事项:\n{todos}\n\n"
        f"转写预览:\n{transcript_preview}\n"
    )

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #1f2937; line-height: 1.7;">
        <h2 style="margin-bottom: 8px;">会议纪要已生成</h2>
        <p>你好，{html.escape(user.username)}：</p>
        <p>以下是系统为你生成的会议纪要。</p>
        <ul>
          <li><strong>Agent:</strong> {html.escape(payload.agent_name or "meeting-secretary-agent")}</li>
          <li><strong>模式:</strong> {html.escape(payload.summary_mode)}</li>
          <li><strong>场景:</strong> {html.escape(payload.scene)}</li>
        </ul>
        <h3>会议摘要</h3>
        <p>{html.escape(payload.summary)}</p>
        <h3>关键词</h3>
        <p>{html.escape(keywords)}</p>
        <h3>待办事项</h3>
        <pre style="white-space: pre-wrap; background: #f8fafc; padding: 12px; border-radius: 8px;">{html.escape(todos)}</pre>
        <h3>转写预览</h3>
        <pre style="white-space: pre-wrap; background: #f8fafc; padding: 12px; border-radius: 8px;">{html.escape(transcript_preview)}</pre>
      </body>
    </html>
    """
    return subject, (text_body, html_body)


def send_summary_email(payload: EmailDeliveryRequest, user: UserProfile) -> EmailDeliveryResponse:
    _require_smtp_settings()

    subject, (text_body, html_body) = _build_email_content(payload, user)

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = (
        f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        if settings.smtp_from_name
        else settings.smtp_from_email
    )
    message["To"] = user.email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30) as server:
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(message)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"邮件发送失败: {exc}",
        ) from exc

    return EmailDeliveryResponse(
        recipient=user.email,
        message="会议纪要已发送到当前登录用户邮箱",
    )
