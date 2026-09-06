from __future__ import annotations

import json
import re
from sqlalchemy.orm import Session

from backend.app.ai.base import get_adapter
from backend.app.repositories.announcement_repo import AnnouncementRepository


def _fallback(title: str, body: str, source_url: str) -> dict:
    text = " ".join(body.split())[:200]
    return {"summary": text or title, "publisher": None, "audience": [], "key_times": [], "deadline": None, "location": None, "todo": [], "evidence": source_url, "status": "degraded"}


class AnnouncementSummaryService:
    @staticmethod
    async def summarize(db: Session, announcement_id: int) -> dict:
        announcement = AnnouncementRepository.get_by_id(db, announcement_id)
        if not announcement:
            raise ValueError("announcement not found")
        prompt = "Return strict JSON with summary,publisher,audience,key_times,deadline,location,todo,evidence. Use only facts in the text."
        try:
            raw = await get_adapter().chat([{"role": "user", "content": f"{announcement.title}\n{announcement.body_text[:12000]}"}], system_prompt=prompt)
            match = re.search(r"\{.*\}", raw, re.S)
            payload = json.loads(match.group(0)) if match else None
            if not isinstance(payload, dict) or not payload.get("summary"):
                raise ValueError("invalid summary JSON")
            payload["status"] = "ready"
        except Exception:
            payload = _fallback(announcement.title, announcement.body_text, "")
        summary = str(payload.get("summary", ""))[:500]
        announcement.summary_text = summary
        announcement.key_fields = {key: payload.get(key) for key in ("publisher", "audience", "key_times", "deadline", "location", "todo") if payload.get(key)}
        announcement.summary_status = payload.get("status", "degraded")
        db.commit()
        return payload

