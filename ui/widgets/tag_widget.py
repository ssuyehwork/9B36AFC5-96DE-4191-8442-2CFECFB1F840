# coding:utf-8
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton


class TagWidget(QWidget):
    removed = pyqtSignal(str)

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 2, 2)
        layout.setSpacing(4)

        self.label = QLabel(self.text)
        self.label.setAttribute(Qt.WA_TranslucentBackground)

        self.close_button = QPushButton("×")
        self.close_button.setObjectName("TagCloseButton") # 关键：应用置零内边距样式
        self.close_button.setFixedSize(16, 16)
        self.close_button.clicked.connect(self.on_remove)

        layout.addWidget(self.label)
        layout.addWidget(self.close_button)

        self.setLayout(layout)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True) # 确保背景色能显示

    def on_remove(self):
        self.removed.emit(self.text)
