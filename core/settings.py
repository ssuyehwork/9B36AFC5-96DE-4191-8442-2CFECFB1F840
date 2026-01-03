# -*- coding: utf-8 -*-
from PyQt5.QtCore import QSettings

def save_setting(key, value):
    """保存设置"""
    settings = QSettings("ClipboardPro", "AppSettings")
    settings.setValue(key, value)

def load_setting(key, default=None):
    """加载设置"""
    settings = QSettings("ClipboardPro", "AppSettings")
    return settings.value(key, default)
