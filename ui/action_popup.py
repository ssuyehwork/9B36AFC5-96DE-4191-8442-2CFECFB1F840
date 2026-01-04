# -*- coding: utf-8 -*-
# ui/action_popup.py

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPoint, QSize
from PyQt5.QtGui import QCursor, QColor
from core.config import COLORS
from ui.common_tags import CommonTags
from ui.success_animation import SuccessAnimationWidget

class ActionPopup(QWidget):
    """
    复制成功后在鼠标附近弹出的快捷操作条
    包含：[图标] | [收藏] [自定义常用标签] [管理]
    """
    request_favorite = pyqtSignal(int)
    request_tag_add = pyqtSignal(int, str)
    request_manager = pyqtSignal() # 请求打开管理界面

    def __init__(self, parent=None): # 不再需要 db
        super().__init__(parent)
        self.current_idea_id = None
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        self._init_ui()
        
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._animate_hide)

    def _init_ui(self):
        self.container = QWidget(self)
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: #2D2D2D;
                border: 1px solid #444;
                border-radius: 18px;
            }}
        """)
        
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)
        
        self.success_animation = SuccessAnimationWidget()
        layout.addWidget(self.success_animation)
        
        line = QLabel("|")
        line.setStyleSheet("color: #555; border:none; background: transparent;")
        layout.addWidget(line)

        self.btn_fav = QPushButton("⭐")
        self.btn_fav.setToolTip("收藏")
        self.btn_fav.setCursor(Qt.PointingHandCursor)
        self.btn_fav.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: #BBB; border: none; font-size: 14px; font-weight: bold; padding: 0px;
            }}
            QPushButton:hover {{ color: {COLORS['warning']}; }}
        """)
        self.btn_fav.clicked.connect(self._on_fav_clicked)
        layout.addWidget(self.btn_fav)

        # 常用标签组件
        self.common_tags_bar = CommonTags()
        self.common_tags_bar.tag_clicked.connect(self._on_quick_tag_clicked)
        # 点击编辑按钮 -> 请求打开管理界面
        self.common_tags_bar.manager_requested.connect(self._on_manager_clicked)
        self.common_tags_bar.refresh_requested.connect(self._adjust_size_dynamically)
        
        layout.addWidget(self.common_tags_bar)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.container.setGraphicsEffect(shadow)

    def _adjust_size_dynamically(self):
        if self.isVisible():
            self.container.adjustSize()
            self.resize(self.container.size() + QSize(10, 10))

    def show_at_mouse(self, idea_id):
        self.current_idea_id = idea_id
        self.common_tags_bar.reload_tags()
        
        self.success_animation.start()
        
        self.btn_fav.setText("⭐")
        self.btn_fav.setStyleSheet(f"QPushButton {{ background: transparent; color: #BBB; border: none; font-size: 14px; }} QPushButton:hover {{ color: {COLORS['warning']}; }}")
        
        self.container.adjustSize()
        self.resize(self.container.size() + QSize(10, 10))
        
        cursor_pos = QCursor.pos()
        x = cursor_pos.x() - self.width() // 2
        y = cursor_pos.y() - 60 
        
        self.move(x, y)
        self.show()
        self.hide_timer.start(3500)

    def _on_fav_clicked(self):
        if self.current_idea_id:
            self.request_favorite.emit(self.current_idea_id)
            self.btn_fav.setText("★")
            self.btn_fav.setStyleSheet(f"color: {COLORS['warning']}; border: none; font-size: 14px;")
            self.hide_timer.start(1000)

    def _on_quick_tag_clicked(self, tag_name):
        if self.current_idea_id:
            self.request_tag_add.emit(self.current_idea_id, tag_name)
            self.hide_timer.start(2500) 

    def _on_manager_clicked(self):
        self.request_manager.emit()
        self.hide() # 打开管理界面时，隐藏悬浮条

    def _animate_hide(self):
        self.hide()

    def enterEvent(self, event):
        self.hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hide_timer.start(1500)
        super().leaveEvent(event)
