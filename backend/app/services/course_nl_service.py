import re
import logging
from datetime import datetime, timedelta
from typing import Any, Optional, cast

from sqlalchemy.orm import Session

from backend.app.repositories.school_repo import CourseRepository, ScheduleRepository
from backend.app.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)

# 周几中文映射
WEEKDAY_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
}


class CourseNLService:
    """自然语言课程查询：解析日期/课程名 → 查结构化课表"""

    @staticmethod
    def parse_date(query: str) -> Optional[int]:
        """
        从查询中解析目标星期几（1-7）
        支持：今天/明天/后天/周X/星期X/礼拜X/本周X
        """
        today = datetime.now()
        today_weekday = today.isoweekday()  # 1-7

        if "今天" in query or "今日" in query:
            return today_weekday
        if "明天" in query or "明日" in query:
            return (today_weekday % 7) + 1
        if "后天" in query:
            return ((today_weekday + 1) % 7) + 1
        if "昨天" in query:
            return ((today_weekday - 2) % 7) + 1

        # 周/星期/礼拜 + 数字/中文
        m = re.search(r"(?:周|星期|礼拜)([一二三四五六日天1-7])", query)
        if m:
            return WEEKDAY_MAP.get(m.group(1))

        return None

    @staticmethod
    def parse_course_name(query: str) -> Optional[str]:
        """尝试提取查询中的课程名关键词（去掉疑问/时间词后剩余的核心词）"""
        # 去除常见疑问/时间/方位词
        cleaned = re.sub(
            r"(今天|明天|后天|昨天|今日|明日|周[一二三四五六日天1-7]|星期[一二三四五六日天1-7]|"
            r"礼拜[一二三四五六日天1-7]|几点|什么时候|哪天|第[一二三四五六七八九十\d]+节|"
            r"上午|下午|有什么|有哪些|有课吗|上课|下课|在第几|在哪|教室|的|是|吗|呢|啊|我|今天|这周|下周)",
            "",
            query,
        )
        cleaned = cleaned.strip()
        return cleaned if len(cleaned) >= 2 else None

    @staticmethod
    def query(db: Session, user_text: str) -> dict:
        """
        解析自然语言并返回结构化课表结果
        返回: {intent, weekday, course_name, results: [...]}
        """
        weekday = CourseNLService.parse_date(user_text)
        course_name = CourseNLService.parse_course_name(user_text)

        # 获取全部课程
        courses, _ = CourseRepository.list(db, page=1, page_size=500)
        course_map = {c.id: c for c in courses}

        results: list[dict[str, Any]] = []

        if course_name:
            # 按课程名搜索：返回该课程所有安排
            intent = "course_search"
            matched = [c for c in courses if course_name in c.name]
            for c in matched:
                schedules = ScheduleRepository.list_by_course(db, c.id)
                for s in schedules:
                    results.append({
                        "course": c.name,
                        "teacher": c.teacher,
                        "weekday": s.weekday,
                        "start_period": s.start_period,
                        "end_period": s.end_period,
                        "location": s.location,
                    })
        elif weekday:
            # 按星期查询当天课程
            intent = "day_schedule"
            course_ids = list(course_map.keys())
            schedules = ScheduleRepository.list_by_weekday(db, weekday, course_ids)
            for s in schedules:
                course = course_map.get(s.course_id)
                if course:
                    results.append({
                        "course": course.name,
                        "teacher": course.teacher,
                        "weekday": s.weekday,
                        "start_period": s.start_period,
                        "end_period": s.end_period,
                        "location": s.location,
                        "start_time": s.start_time,
                        "end_time": s.end_time,
                    })
            results.sort(key=lambda item: cast(int, item["start_period"]))
        else:
            intent = "unknown"

        weekday_names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return {
            "intent": intent,
            "weekday": weekday,
            "weekday_name": weekday_names[weekday] if weekday else None,
            "course_name": course_name,
            "count": len(results),
            "results": results,
        }
