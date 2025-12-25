# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QScrollArea, QGridLayout, QPushButton, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

class TagPopup(QWidget):
    """
    动态标签选择/创建弹窗
    """
    tag_selected = pyqtSignal(str, bool)  # 选中/取消选中 (tag_name, is_checked)
    create_tag_requested = pyqtSignal(str) # 请求创建新标签
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 布局容器
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10) # 预留阴影空间
        self.main_layout.setSpacing(0)
        
        self.container = QFrame()
        self.container.setObjectName("TagPopupContainer")
        self.container.setAttribute(Qt.WA_StyledBackground, True)
        
        # 增加物理阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.container.setGraphicsEffect(shadow)
        
        self.layout_container = QVBoxLayout(self.container)
        self.layout_container.setContentsMargins(8, 8, 8, 8) # 增加内边距
        self.layout_container.setSpacing(6)
        
        # 1. 创建模式视图 (顶部)
        self.creation_view = QFrame()
        self.creation_layout = QVBoxLayout(self.creation_view)
        self.creation_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_create = QPushButton()
        self.btn_create.setCursor(Qt.PointingHandCursor)
        self.btn_create.setObjectName("TagCreateButton") # 设置ObjectName
        self.btn_create.clicked.connect(self._on_create_clicked)
        self.creation_layout.addWidget(self.btn_create)
        self.layout_container.addWidget(self.creation_view)
        
        # 2. 历史模式视图 (下部)
        self.history_view = QWidget()
        self.history_layout = QVBoxLayout(self.history_view)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(5)
        
        self.lbl_history = QLabel("最近使用")
        self.lbl_history.setObjectName("TagPopupHeader") # 设置ObjectName
        self.history_layout.addWidget(self.lbl_history)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("background: transparent;")

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(2, 2, 2, 2)
        self.grid_layout.setSpacing(4)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll.setWidget(self.grid_widget)

        self.history_layout.addWidget(self.scroll, 1) # 赋予权重 1
        self.layout_container.addWidget(self.history_view, 1) # 赋予权重 1
        
        self.main_layout.addWidget(self.container)
        
        # 底部提示
        self.lbl_tip = QLabel("移动: ↑↓  选中: Enter  关闭: Esc")
        self.lbl_tip.setAlignment(Qt.AlignRight)
        self.lbl_tip.setObjectName("TagPopupTip") # 设置ObjectName
        self.layout_container.addWidget(self.lbl_tip)
        
        # 数据缓存
        self.current_tags = [] # list of (name, count)
        self.selected_tags = set()
        self.typing_text = ""

    def load_history(self, tags, active_tags=None):
        """加载初始数据"""
        self.current_tags = tags
        if active_tags:
            self.selected_tags = set(active_tags)
        
        self._populate_grid(self.current_tags)
        self.lbl_history.setText(f"最近使用 ({len(tags)})")
        
        self.creation_view.hide()
        self.history_view.show()

    def filter_ui(self, text):
        """核心逻辑：根据输入文本过滤UI"""
        text = text.strip()
        self.typing_text = text
        
        filtered_tags = []
        is_exact_match = False
        
        if not text:
            filtered_tags = self.current_tags
        else:
            for name, count in self.current_tags:
                if text.lower() in name.lower():
                    filtered_tags.append((name, count))
                if text.lower() == name.lower():
                    is_exact_match = True
        
        self._populate_grid(filtered_tags)
        
        if not text:
            self.lbl_history.setText(f"最近使用 ({len(filtered_tags)})")
        else:
            self.lbl_history.setText("搜索结果")

        if text and not is_exact_match:
            self.creation_view.show()
            self.btn_create.setText(f"+ 新建标签 \"{text}\"")
        else:
            self.creation_view.hide()
            
        if filtered_tags:
            self.history_view.show()
        else:
            self.history_view.hide()

    def _populate_grid(self, tags):
        """填充网格"""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        row, col = 0, 0
        for name, count in tags:
            btn = self._create_tag_btn(name, count)
            self.grid_layout.addWidget(btn, row, col)
            
            col += 1
            if col > 1:
                col = 0
                row += 1
                
        self._refresh_check_state()

    def _create_tag_btn(self, name, count):
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setProperty("tag_name", name)
        btn.setObjectName("TagPopupButton") # 设置ObjectName
        
        btn.setText(f"🕒 {name}") # 恢复时钟符号
        btn.setToolTip(f"引用次数: {count}")
        
        btn.clicked.connect(lambda checked, n=name: self._on_tag_clicked(n, checked))
        return btn

    def _refresh_check_state(self):
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                btn = item.widget()
                name = btn.property("tag_name")
                is_sel = name in self.selected_tags
                btn.setChecked(is_sel)
                
                if is_sel:
                    btn.setText(f"🕒 {name}") # 恢复时钟，但保持移除 ✅
                else:
                    btn.setText(f"🕒 {name}") # 恢复时钟

    def _on_tag_clicked(self, name, checked):
        if checked:
            self.selected_tags.add(name)
        else:
            self.selected_tags.discard(name)
        
        self._refresh_check_state()
        self.tag_selected.emit(name, checked)

    def _on_create_clicked(self):
        if self.typing_text:
            self.create_tag_requested.emit(self.typing_text)
            self.hide()
