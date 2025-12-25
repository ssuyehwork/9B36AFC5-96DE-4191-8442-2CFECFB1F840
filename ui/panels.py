# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel, QLineEdit, QPushButton, QHBoxLayout, QScrollArea
from PyQt5.QtCore import Qt, pyqtSignal

class DetailPanel(QWidget):
    update_note_signal = pyqtSignal(str)
    add_tag_signal = pyqtSignal()
    remove_tag_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("选择条目以预览...")
        self.layout.addWidget(self.preview, 1)
        
        self.layout.addWidget(QLabel("📝 备注:"))
        self.note_edit = QLineEdit()
        self.note_edit.returnPressed.connect(lambda: self.update_note_signal.emit(self.note_edit.text()))
        self.layout.addWidget(self.note_edit)
        
        self.layout.addSpacing(15)
        self.layout.addWidget(QLabel("🏷️ 当前标签:"))
        self.tag_container = QWidget()
        self.tag_layout = QHBoxLayout(self.tag_container)
        self.tag_layout.setAlignment(Qt.AlignLeft)
        self.tag_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.tag_container)
        scroll.setFixedHeight(60)
        scroll.setStyleSheet("border: none; background: transparent;")
        self.layout.addWidget(scroll)
        
        btn_add = QPushButton("+ 添加标签")
        btn_add.clicked.connect(self.add_tag_signal.emit)
        self.layout.addWidget(btn_add)
        
    def load_item(self, content, note, tags):
        self.preview.setText(content)
        self.note_edit.setText(note)
        for i in reversed(range(self.tag_layout.count())): 
            self.tag_layout.itemAt(i).widget().deleteLater()
            
        for tag_name in tags:
            btn = QPushButton(f"{tag_name} ✕")
            btn.setStyleSheet("QPushButton { background: #313244; border-radius: 10px; padding: 2px 8px; color: #89b4fa; border: 1px solid #89b4fa; } QPushButton:hover { background: #45475a; color: #f38ba8; border-color: #f38ba8; }")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, t=tag_name: self.remove_tag_signal.emit(t))
            self.tag_layout.addWidget(btn)