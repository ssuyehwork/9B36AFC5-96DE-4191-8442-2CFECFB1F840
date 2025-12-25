# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QLineEdit, QColorDialog

class TagDialog(QDialog):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.selected_tag = None
        self.setWindowTitle("标签管理")
        self.resize(300, 400)
        layout = QVBoxLayout(self)
        
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入新标签...")
        self.input.returnPressed.connect(self.accept_input)
        layout.addWidget(self.input)
        
        self.list = QListWidget()
        self.list.itemClicked.connect(self.item_clicked)
        layout.addWidget(self.list)
        self.refresh_list()
        
    def refresh_list(self):
        self.list.clear()
        tags = self.db.get_stats()['tags']
        for name, count in tags: self.list.addItem(f"{name}")

    def accept_input(self):
        text = self.input.text().strip()
        if text: self.selected_tag = text; self.accept()

    def item_clicked(self, item):
        self.selected_tag = item.text(); self.accept()

class ColorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = None
        self.setWindowTitle("选择颜色")
        layout = QVBoxLayout(self)
        grid = QHBoxLayout()
        for c in ["#f38ba8", "#f9e2af", "#a6e3a1", "#89b4fa", "#cba6f7"]:
            btn = QPushButton()
            btn.setFixedSize(30, 30)
            btn.setObjectName("ColorDialogButton")
            btn.setProperty("color", c) # 使用setProperty存储颜色
            btn.clicked.connect(lambda _, col=c: self.done_color(col))
            grid.addWidget(btn)
        layout.addLayout(grid)
        sys_btn = QPushButton("更多颜色...")
        sys_btn.clicked.connect(self.pick_sys)
        layout.addWidget(sys_btn)
        
    def done_color(self, c): self.color = c; self.accept()
    def pick_sys(self):
        c = QColorDialog.getColor()
        if c.isValid(): self.color = c.name(); self.accept()
