
import sys
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QTextEdit,
    QHBoxLayout, QPushButton, QWidget
)
from PyQt5.QtCore import Qt


class NewIdeaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建灵感")
        self.setMinimumSize(400, 300)

        # Main layout
        main_layout = QVBoxLayout(self)

        # Text edit for multi-line input
        self.text_edit = QTextEdit(self)
        self.text_edit.setPlaceholderText("在这里输入你的灵感...")
        main_layout.addWidget(self.text_edit)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch() # Push buttons to the right

        # Buttons
        self.cancel_button = QPushButton("取消", self)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.save_button = QPushButton("保存", self)
        self.save_button.setDefault(True) # Default button (e.g., triggered by Enter)
        self.save_button.clicked.connect(self.accept)
        button_layout.addWidget(self.save_button)

        # Add button layout to main layout
        main_layout.addLayout(button_layout)

    def get_idea_text(self):
        """Returns the text entered in the dialog."""
        return self.text_edit.toPlainText().strip()

