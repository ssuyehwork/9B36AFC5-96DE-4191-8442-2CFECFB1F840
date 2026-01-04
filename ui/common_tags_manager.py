# -*- coding: utf-8 -*-
# ui/common_tags_manager.py

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QLineEdit, QPushButton, QLabel, QListWidgetItem, 
                             QMessageBox, QAbstractItemView, QSpinBox, QCheckBox, QWidget, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor
from core.config import COLORS
from core.settings import load_setting, save_setting

class CommonTagsManager(QDialog):
    """
    常用标签管理界面 (现代卡片风格版)
    - 视觉升级：独立的圆角卡片列表，去除传统网格感
    - 修复：滚动条样式统一为现代极简风格
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 加载数据
        raw_tags = load_setting('manual_common_tags', ['工作', '待办', '重要'])
        self.tags_data = []
        for item in raw_tags:
            if isinstance(item, str):
                self.tags_data.append({'name': item, 'visible': True})
            elif isinstance(item, dict):
                self.tags_data.append(item)
                
        self.limit = load_setting('common_tags_limit', 5)
        
        self.setWindowTitle("🏷️ 管理常用标签")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(340, 520) 
        
        self._init_ui()
        self._refresh_list()

    def _init_ui(self):
        # 主容器
        container = QWidget(self)
        container.setGeometry(10, 10, 320, 500) 
        container.setStyleSheet(f"""
            QWidget {{
                background-color: #1E1E1E;
                border: 1px solid #333;
                border-radius: 12px;
                color: #EEE;
            }}
        """)
        
        # 窗口阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 100))
        container.setGraphicsEffect(shadow)

        # --- 主布局 ---
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 1. 顶部标题栏 (标题 + 关闭按钮)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("管理常用标签")
        title.setStyleSheet("font-weight: bold; font-size: 15px; border: none; color: #DDD;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.btn_close = QPushButton("×")
        self.btn_close.setFixedSize(32, 32)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("保存并关闭")
        self.btn_close.clicked.connect(self._save_and_close)
        self.btn_close.setStyleSheet("""
            QPushButton { 
                background-color: transparent; 
                border: none; 
                font-size: 20px; 
                color: #888; 
                font-family: Arial;
                border-radius: 4px;
            } 
            QPushButton:hover { 
                background-color: #E81123; 
                color: white; 
            }
        """)
        header_layout.addWidget(self.btn_close)
        
        layout.addLayout(header_layout)
        
        # 2. 输入区
        input_container = QWidget()
        input_container.setStyleSheet("background: transparent; border: none;")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)
        
        self.inp_tag = QLineEdit()
        self.inp_tag.setPlaceholderText("输入新标签...")
        self.inp_tag.setStyleSheet(f"""
            QLineEdit {{
                background-color: #2D2D2D; 
                border: 1px solid #444; 
                border-radius: 6px; 
                padding: 8px 10px; 
                color: white;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {COLORS['primary']}; background-color: #333; }}
        """)
        self.inp_tag.returnPressed.connect(self._add_tag)
        
        btn_add = QPushButton("添加")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']}; 
                color: white; 
                border: none; 
                border-radius: 6px; 
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: #357ABD; }}
        """)
        btn_add.clicked.connect(self._add_tag)
        
        input_layout.addWidget(self.inp_tag)
        input_layout.addWidget(btn_add)
        layout.addWidget(input_container)
        
        # 3. 数量限制
        limit_layout = QHBoxLayout()
        lbl_limit = QLabel("悬浮条最大显示数量:")
        lbl_limit.setStyleSheet("color: #AAA; font-size: 12px; border:none;")
        
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 10)
        self.spin_limit.setValue(self.limit)
        self.spin_limit.setFixedWidth(60)
        self.spin_limit.setStyleSheet("""
            QSpinBox { 
                background-color: #2D2D2D; 
                border: 1px solid #444; 
                color: white; 
                padding: 4px; 
                border-radius: 4px; 
            }
            QSpinBox:focus { border-color: #555; }
            QSpinBox::up-button, QSpinBox::down-button { background: none; border: none; }
        """)
        
        limit_layout.addWidget(lbl_limit)
        limit_layout.addWidget(self.spin_limit)
        limit_layout.addStretch()
        layout.addLayout(limit_layout)
        
        # 4. 列表区
        lbl_hint = QLabel("💡 拖拽调整顺序，勾选控制显示")
        lbl_hint.setStyleSheet("color: #666; font-size: 11px; border:none; margin-bottom: 5px;")
        layout.addWidget(lbl_hint)

        self.list_widget = QListWidget()
        # 【关键修复】在此处注入 QScrollBar 样式，覆盖系统默认
        self.list_widget.setStyleSheet(f"""
            QListWidget {{ 
                background-color: transparent; 
                border: none; 
                outline: none; 
            }}
            QListWidget::item {{ 
                background-color: #2D2D2D; 
                color: #DDD; 
                border: 1px solid #3A3A3A;
                border-radius: 8px; 
                margin-bottom: 6px; 
                padding: 8px 10px; 
            }}
            QListWidget::item:hover {{ 
                background-color: #333333; 
                border: 1px solid #555;
            }}
            QListWidget::item:selected {{ 
                background-color: #2D2D2D; 
                border: 1px solid {COLORS['primary']}; 
                color: white; 
            }}
            QListWidget::indicator {{ 
                width: 16px; height: 16px; 
                border-radius: 4px; 
                border: 1px solid #666; 
                background: transparent;
            }}
            QListWidget::indicator:checked {{ 
                background-color: {COLORS['primary']}; 
                border-color: {COLORS['primary']}; 
                image: url(none); 
            }}
            
            /* --- 现代滚动条样式修复 --- */
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 6px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #444;
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #555;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)
        
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.MoveAction)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel) 
        
        layout.addWidget(self.list_widget)
        
        # 5. 底部按钮
        btn_del = QPushButton("删除选中项")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(231, 76, 60, 0.1); 
                color: {COLORS['danger']}; 
                border: 1px solid {COLORS['danger']}; 
                border-radius: 6px; 
                padding: 8px;
                font-size: 13px;
            }}
            QPushButton:hover {{ 
                background-color: {COLORS['danger']}; 
                color: white; 
            }}
        """)
        btn_del.clicked.connect(self._del_tag)
        layout.addWidget(btn_del)
        
        # 拖拽窗口支持
        self.drag_pos = None

    def _refresh_list(self):
        """将数据渲染到列表"""
        self.list_widget.clear()
        for tag_data in self.tags_data:
            item = QListWidgetItem(tag_data['name'])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            state = Qt.Checked if tag_data.get('visible', True) else Qt.Unchecked
            item.setCheckState(state)
            self.list_widget.addItem(item)

    def _add_tag(self):
        text = self.inp_tag.text().strip()
        if not text: return
        
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).text() == text:
                QMessageBox.warning(self, "提示", "该标签已存在")
                return
        
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
        item.setCheckState(Qt.Checked)
        self.list_widget.addItem(item)
        self.inp_tag.clear()
        self.list_widget.scrollToBottom()

    def _del_tag(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)

    def _save_and_close(self):
        new_tags_data = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            new_tags_data.append({
                'name': item.text(),
                'visible': (item.checkState() == Qt.Checked)
            })
            
        save_setting('manual_common_tags', new_tags_data)
        save_setting('common_tags_limit', self.spin_limit.value())
        self.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos:
            self.move(event.globalPos() - self.drag_pos)
            event.accept()
