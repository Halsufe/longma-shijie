import csv
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import hash_password
from backend.app.models.user import User
from backend.app.models.user_session import UserSession
from backend.app.models.achievement import Achievement
from backend.app.models.resource import Resource
from backend.app.models.party import PartyActivity


def parse_import(content: bytes, db: Session | None = None) -> dict:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows, summary = [], {"create": 0, "update": 0, "restore": 0, "skip": 0, "error": 0}
    if not reader.fieldnames or not ({"学号", "student_no"} & set(reader.fieldnames)):
        raise ValueError("CSV 必须包含学号列")
    seen: set[str] = set()
    for line, row in enumerate(reader, 2):
        student_no = (row.get("学号") or row.get("student_no") or "").strip()
        name = (row.get("姓名") or row.get("name") or "").strip()
        role = (row.get("角色") or row.get("role") or "student").strip()
        action, error = "create", None
        if student_no in seen and student_no:
            action = "skip"
        seen.add(student_no)
        if db is not None and student_no:
            existing = db.query(User).filter(User.student_no == student_no).first()
            if existing and action != "skip":
                action = "restore" if existing.deleted_at is not None else "update"
        if not student_no or not name or role not in ("student", "alumni", "teacher", "admin"):
            action, error = "error", "学号、姓名或角色无效"
        summary[action] += 1
        rows.append({"line": line, "student_no": student_no, "name": name, "role": role, "action": action, "error": error})
    if len(rows) > 1000:
        raise ValueError("单次导入不能超过 1000 行")
    return {"rows": rows, "summary": summary}


def import_token(content: bytes, parsed: dict) -> str:
    summary_hash = hashlib.sha256(json.dumps(parsed["summary"], sort_keys=True).encode()).hexdigest()
    payload = {"type": "user_import", "file_sha256": hashlib.sha256(content).hexdigest(), "row_count": len(parsed["rows"]), "summary_hash": summary_hash, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def confirm_import(db: Session, content: bytes, token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("预检令牌无效或已过期") from exc
    if payload.get("type") != "user_import" or payload.get("file_sha256") != hashlib.sha256(content).hexdigest():
        raise ValueError("上传文件与预检文件不一致")
    parsed = parse_import(content, db)
    summary_hash = hashlib.sha256(json.dumps(parsed["summary"], sort_keys=True).encode()).hexdigest()
    if payload.get("row_count") != len(parsed["rows"]) or payload.get("summary_hash") != summary_hash:
        raise ValueError("预检摘要与文件内容不一致")
    if any(row["action"] == "error" for row in parsed["rows"]):
        raise ValueError("文件包含错误行，未导入任何数据")
    created = updated = 0
    for row in parsed["rows"]:
        if row["action"] in {"error", "skip"}:
            continue
        user = db.query(User).filter(User.student_no == row["student_no"]).first()
        if user:
            user.name, user.role, user.deleted_at = row["name"], row["role"], None
            updated += 1
        else:
            db.add(User(student_no=row["student_no"], name=row["name"], role=row["role"], status="pending_change", password_hash=hash_password("123456")))
            created += 1
    db.commit()
    return {"created": created, "updated": updated}


def export_users(db: Session, q: str | None, role: str | None, status: str | None) -> bytes:
    query = db.query(User).filter(User.deleted_at.is_(None))
    if q:
        query = query.filter((User.student_no.ilike(f"%{q}%")) | (User.name.ilike(f"%{q}%")))
    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.status == status)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["学号", "姓名", "角色", "状态", "毕业年份"])
    writer.writerows((u.student_no, u.name, u.role, u.status, u.graduation_year or "") for u in query.order_by(User.id).all())
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def activity_stats(db: Session, days: int) -> list[dict]:
    now = datetime.now(timezone(timedelta(hours=8)))
    result = []
    for offset in reversed(range(days)):
        day = (now - timedelta(days=offset)).date()
        start = datetime.combine(day, datetime.min.time(), tzinfo=now.tzinfo)
        end = start + timedelta(days=1)
        count = db.query(func.count(func.distinct(UserSession.user_id))).filter(UserSession.last_active_at >= start, UserSession.last_active_at < end).scalar() or 0
        result.append({"date": day.isoformat(), "dau": count})
    return result


def business_stats(db: Session, year: int | None = None, category: str | None = None) -> dict:
    party_query = db.query(PartyActivity).filter(PartyActivity.deleted_at.is_(None))
    if year:
        party_query = party_query.filter(func.strftime("%Y", PartyActivity.start_at) == str(year))
    if category:
        party_query = party_query.filter(PartyActivity.category == category)
    resource_query = db.query(Resource).filter(Resource.type == "competition", Resource.deleted_at.is_(None))
    if category and category != "competition":
        resource_query = resource_query.filter(Resource.id == -1)
    achievement_query = db.query(Achievement).filter(Achievement.deleted_at.is_(None), Achievement.status == "approved")
    if year:
        achievement_query = achievement_query.filter(Achievement.achievement_date.like(f"{year}%"))
    return {
        "party": {"status": "available", "activities": party_query.count(), "details": []},
        "competition": {"status": "available", "resources": resource_query.count(), "details": []},
        "achievements": {"status": "available", "total": achievement_query.count(), "details": []},
    }
