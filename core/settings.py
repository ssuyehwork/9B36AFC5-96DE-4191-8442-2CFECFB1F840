# -*- coding: utf-8 -*-
# core/settings.py

from PyQt5.QtCore import QSettings

def load_setting(key, default=None):
    """
    Helper function to load a setting from QSettings.
    """
    settings = QSettings("MyTools", "ClipboardPro")
    return settings.value(key, default)

def save_setting(key, value):
    """
    Helper function to save a setting to QSettings.
    """
    settings = QSettings("MyTools", "ClipboardPro")
    settings.setValue(key, value)
