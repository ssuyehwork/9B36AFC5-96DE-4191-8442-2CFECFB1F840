# -*- coding: utf-8 -*-
from PyQt5.QtGui import QColor, QPixmap, QIcon, QPainter
from PyQt5.QtCore import Qt

# 这个文件现在变得很干净，只存放逻辑工具，不存放一大串CSS代码了

def format_size(text):
    """格式化显示大小"""
    if not text: return "0 B"
    b = len(text.encode('utf-8'))
    if b < 1024: return f"{b} B"
    elif b < 1024**2: return f"{b/1024:.1f} KB"
    else: return f"{b/1024**2:.1f} MB"

def get_color_icon(hex_color):
    """生成颜色圆点图标"""
    if not hex_color: return QIcon()
    px = QPixmap(16, 16)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(hex_color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(1, 1, 14, 14)
    p.end()
    return QIcon(px)