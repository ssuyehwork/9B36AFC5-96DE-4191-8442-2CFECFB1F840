# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

def get_date_label(dt: datetime) -> str | None:
    """
    根据给定的 datetime 对象生成一个用户友好的日期标签。
    例如："今日", "昨日", "周内", "本月" 等。
    """
    if not isinstance(dt, datetime):
        return None

    today = datetime.now().date()

    # 确保我们比较的是 date 对象
    dt_date = dt.date()

    if dt_date == today:
        return "今日"
    if dt_date == today - timedelta(days=1):
        return "昨日"
    if dt_date >= today - timedelta(days=7):
        return "周内"
    if dt_date >= today - timedelta(days=14):
        return "两周"

    # 月份比较
    if dt_date.year == today.year and dt_date.month == today.month:
        return "本月"

    # 上个月
    first_day_of_current_month = today.replace(day=1)
    last_day_of_last_month = first_day_of_current_month - timedelta(days=1)
    first_day_of_last_month = last_day_of_last_month.replace(day=1)
    if first_day_of_last_month <= dt_date <= last_day_of_last_month:
        return "上月"

    return None
