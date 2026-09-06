from __future__ import annotations
import hashlib
import re
from difflib import SequenceMatcher

def normalize_title(title: str) -> str:
    return re.sub(r"[\s\u3000\-_|:：，。,.、]+", "", (title or "").strip()).lower()

def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join((text or "").split()).encode("utf-8")).hexdigest()

def similar_titles(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_title(left), normalize_title(right)).ratio()

def is_relevant(title: str, body: str = "") -> bool | None:
    text = f"{title} {body}"
    if any(word in text for word in ("采购", "招标", "招聘", "招生宣传", "校外新闻", "喜报")):
        return False
    if any(word in text for word in ("考试", "课程", "选课", "奖学金", "放假", "报名", "学生", "教学", "学籍", "竞赛")):
        return True
    return None

