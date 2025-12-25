# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (QWidget, QLayout, QLineEdit, QLabel, QPushButton, 
                             QFrame, QVBoxLayout, QHBoxLayout, QSizePolicy)
from PyQt5.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal, QEvent
from PyQt5.QtGui import QPalette, QColor

class FlowLayout(QLayout):
    """流式布局"""
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent is not None: 
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []
        
    def __del__(self):
        item = self.takeAt(0)
        while item: 
            item = self.takeAt(0)
            
    def addItem(self, item): 
        self.itemList.append(item)
        
    def count(self): 
        return len(self.itemList)
        
    def itemAt(self, index): 
        return self.itemList[index] if 0 <= index < len(self.itemList) else None
        
    def takeAt(self, index): 
        return self.itemList.pop(index) if 0 <= index < len(self.itemList) else None
        
    def expandingDirections(self): 
        return Qt.Orientations(Qt.Orientation(0))
        
    def hasHeightForWidth(self): 
        return True
        
    def heightForWidth(self, width): 
        return self._doLayout(QRect(0, 0, width, 0), True)
        
    def setGeometry(self, rect): 
        super().setGeometry(rect)
        self._doLayout(rect, False)
        
    def sizeHint(self): 
        return self.minimumSize()
        
    def minimumSize(self):
        size = QSize()
        for item in self.itemList: 
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size
        
    def _doLayout(self, rect, testOnly):
        x, y = rect.x(), rect.y()
        lineHeight = 0
        spacing = self.spacing()
        
        for item in self.itemList:
            wid = item.widget()
            spaceX = spacing + wid.style().layoutSpacing(
                QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal)
            spaceY = spacing + wid.style().layoutSpacing(
                QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical)
            nextX = x + item.sizeHint().width() + spaceX
            
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0
                
            if not testOnly: 
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())
            
        return y + lineHeight - rect.y()


class TagChip(QFrame):
    """标签胶囊组件"""
    remove_requested = pyqtSignal()
    
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(4)
        
        self.lbl = QLabel(text)
        layout.addWidget(self.lbl)
        
        self.btn = QPushButton("×")
        self.btn.setObjectName("TagCloseButton")
        self.btn.setFixedSize(14, 14) # 稍微减小尺寸以适配 24px 高度
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(self.remove_requested.emit)
        layout.addWidget(self.btn)
        
        self.setFixedHeight(24)
        self.setMinimumWidth(40) # 仅设置最小宽度，允许其水平伸缩
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed) # 关键：让尺寸策略随内容伸缩
        self.setAutoFillBackground(True)
        
    def text(self): 
        return self.lbl.text()


class TagInputWidget(QFrame):
    """
    标签输入组件
    上方：Tag Chip 显示区（暂存区）
    下方：输入框
    """
    tags_committed = pyqtSignal(list)
    tags_changed = pyqtSignal(list)
    text_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TagInputWidget") # 设置ObjectName
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.IBeamCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 6, 8, 6)
        self.main_layout.setSpacing(6)
        
        self.chips_container = QWidget()
        self.chips_container.setObjectName("ChipsContainer") # 设置ObjectName
        self.flow_layout = FlowLayout(self.chips_container, margin=0, spacing=4)
        self.main_layout.addWidget(self.chips_container)
        
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("为选中项添加标签(回车)...")
        self.line_edit.setFrame(False)
        
        palette = self.line_edit.palette()
        palette.setColor(QPalette.PlaceholderText, QColor("#a6adc8")) # 使用调色板中的次要文本色
        self.line_edit.setPalette(palette)
        
        self.line_edit.textChanged.connect(self._on_text_changed)
        self.line_edit.returnPressed.connect(self._on_return)
        self.line_edit.installEventFilter(self)
        
        self.main_layout.addWidget(self.line_edit)
        
        self.chips = []
        
        self._update_chips_visibility()

    def mousePressEvent(self, event):
        self.line_edit.setFocus()
        super().mousePressEvent(event)

    def eventFilter(self, obj, event):
        if obj == self.line_edit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Backspace and not self.line_edit.text() and self.chips:
                self.remove_chip(self.chips[-1])
                return True
            elif event.text() in (',', '，'):
                text = self.line_edit.text().strip()
                if text:
                    self.add_chip(text)
                    self.line_edit.clear()
                return True
        return super().eventFilter(obj, event)

    def _on_text_changed(self, text):
        if text.endswith(',') or text.endswith('，'):
            content = text[:-1].strip()
            if content:
                self.add_chip(content)
            self.line_edit.clear()
            return
        self.text_changed.emit(text)

    def _on_return(self):
        text = self.line_edit.text().strip()
        if text:
            self.add_chip(text)
            self.line_edit.clear()
        elif self.chips:
            self.tags_committed.emit([c.text() for c in self.chips])
            self.clear_chips()

    def add_chip(self, text):
        if any(c.text() == text for c in self.chips):
            return
        
        chip = TagChip(text, self.chips_container)
        chip.remove_requested.connect(lambda: self.remove_chip(chip))
        self.flow_layout.addWidget(chip)
        self.chips.append(chip)
        
        self._update_ui_state()

    def remove_chip(self, chip):
        if chip in self.chips:
            self.chips.remove(chip)
            self.flow_layout.removeWidget(chip)
            chip.deleteLater()
            self._update_ui_state()

    def clear_chips(self):
        while self.chips:
            self.remove_chip(self.chips[0])

    def _update_ui_state(self):
        """统一更新UI状态"""
        has_chips = bool(self.chips)
        self.chips_container.setVisible(has_chips)
        
        if has_chips:
            self.line_edit.setPlaceholderText("继续输入...")
        else:
            self.line_edit.setPlaceholderText("为选中项添加标签(回车)...")
        
        self.tags_changed.emit([c.text() for c in self.chips])
        self.chips_container.updateGeometry()
        self.updateGeometry()

    def _update_chips_visibility(self):
        self.chips_container.setVisible(bool(self.chips))

    def clear_text(self): 
        self.line_edit.clear()
        
    def get_tags(self): 
        return [c.text() for c in self.chips]
        
    def set_focus(self): 
        self.line_edit.setFocus()
        
    def current_text(self): 
        return self.line_edit.text()
