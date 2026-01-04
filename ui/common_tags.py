# -*- coding: utf-8 -*-
# ui/common_tags.py

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal
from core.config import COLORS
from core.settings import load_setting

class CommonTags(QWidget):
    """
    嵌入式常用标签栏 (智能版)
    - 读取用户自定义的顺序和显隐设置
    - 遵守数量限制
    """
    tag_clicked = pyqtSignal(str) # 点击某个标签
    manager_requested = pyqtSignal()   # 点击编辑按钮
    refresh_requested = pyqtSignal()   # 请求刷新尺寸

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.reload_tags()

    def _init_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def reload_tags(self):
        """从配置加载，并根据显隐和数量限制进行渲染"""
        # 清除旧按钮
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 1. 加载数据
        raw_tags = load_setting('manual_common_tags', ['工作', '待办', '重要'])
        limit = load_setting('common_tags_limit', 5) # 默认显示5个

        # 2. 数据清洗 (兼容旧格式字符串列表)
        processed_tags = []
        for item in raw_tags:
            if isinstance(item, str):
                processed_tags.append({'name': item, 'visible': True})
            elif isinstance(item, dict):
                processed_tags.append(item)
        
        # 3. 筛选可见标签
        visible_tags = [t for t in processed_tags if t.get('visible', True)]
        
        # 4. 截取前 N 个
        display_tags = visible_tags[:limit]

        # 5. 渲染按钮
        for tag in display_tags:
            name = tag['name']
            btn = QPushButton(f"{name}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #3E3E42;
                    color: #DDD;
                    border: 1px solid #555;
                    border-radius: 10px;
                    padding: 2px 8px;
                    font-size: 11px;
                    min-height: 20px;
                    max-width: 80px; 
                }}
                QPushButton:hover {{
                    background-color: {COLORS['primary']};
                    border-color: {COLORS['primary']};
                    color: white;
                }}
            """)
            btn.clicked.connect(lambda _, n=name: self.tag_clicked.emit(n))
            self.layout.addWidget(btn)

        # 编辑按钮 (始终显示在最后)
        btn_edit = QPushButton("✎")
        btn_edit.setToolTip("管理常用标签 (排序/显隐/数量)")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #888;
                border: 1px solid #666;
                border-radius: 10px;
                width: 20px;
                height: 20px;
                padding: 0px;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background-color: #444;
                color: white;
            }}
        """)
        btn_edit.clicked.connect(self.manager_requested.emit)
        self.layout.addWidget(btn_edit)
        
        # 通知父级刷新尺寸
        self.refresh_requested.emit()
