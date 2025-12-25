# -*- coding: utf-8 -*-
"""
浅色主题样式表
"""

STYLESHEET = """
/* =======================================================
   全局基础设定
   ======================================================= */
* {
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 14px;
    outline: none;
}

QWidget {
    background-color: #ffffff;
    color: #333333;
}

/* =======================================================
   主窗口容器
   ======================================================= */
#MainFrame {
    background-color: #f3f3f3;
    border: 1px solid #cccccc;
    border-radius: 8px;
}

/* =======================================================
   标题栏
   ======================================================= */
CustomTitleBar {
    background-color: #ffffff;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    border-bottom: 1px solid #e0e0e0;
}

#WindowTitle {
    font-weight: bold;
    font-size: 14px;
    color: #555555;
    background: transparent;
}

#WindowControlButton, #WindowCloseButton {
    background: transparent;
    color: #666666;
}
#WindowControlButton:hover { background-color: #e5e5e5; color: #000000; }
#WindowCloseButton:hover { background-color: #e81123; color: white; }

#ToolbarSearchBar {
    background-color: #f0f0f0;
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    color: #333333;
}
#ToolbarSearchBar:focus {
    background-color: #ffffff;
    border: 1px solid #0078d4;
}

#ToolBarButton {
    background: transparent;
    color: #666666;
    border: 1px solid transparent;
}
#ToolBarButton:hover { background-color: #f0f0f0; }
#ToolBarButton:checked { background-color: #e6f7ff; color: #0078d4; border: 1px solid #1890ff; }

/* =======================================================
   Dock 面板
   ======================================================= */
#CustomDockTitleBar {
    background-color: #f9f9f9;
    border-bottom: 1px solid #e0e0e0;
}
#customDockLabel {
    color: #333333;
    font-weight: bold;
}
#customDockMenuButton {
    background: transparent;
    color: #666666;
}
#customDockMenuButton:hover { background-color: #e5e5e5; }

QMainWindow::separator {
    background-color: #e0e0e0;
}

/* =======================================================
   列表/表格/树
   ======================================================= */
QTableWidget, QTreeWidget {
    background-color: #ffffff;
    border: none;
    alternate-background-color: #fcfcfc;
}

QTableWidget::item:hover, QTreeWidget::item:hover {
    background-color: #f0f0f0;
}

QTableWidget::item:selected, QTreeWidget::item:selected {
    background-color: #e6f7ff;
    color: #000000;
}

QHeaderView::section {
    background-color: #f9f9f9;
    color: #555555;
    border: none;
    border-right: 1px solid #e0e0e0;
    border-bottom: 1px solid #e0e0e0;
}

/* =======================================================
   输入控件 & 详情
   ======================================================= */
#NoteInput, #PreviewBox, #TagInputWidget QLineEdit {
    background-color: #ffffff;
    border: 1px solid #d9d9d9;
    color: #333333;
}
#NoteInput:focus, #PreviewBox:focus, #TagInputWidget QLineEdit:focus {
    border: 1px solid #0078d4;
}

#TagInputWidget {
    background-color: #ffffff;
    border: 1px solid #d9d9d9;
    border-radius: 6px;
}
#TagInputWidget:focus-within {
    border: 1px solid #0078d4;
}

/* Tag Chips */
#ChipsContainer QFrame {
    background-color: #e6e6e6;
    border: 1px solid #cccccc;
    border-radius: 12px;
    color: #333333;
}
#TagCloseButton {
    color: #666666;
}
#TagCloseButton:hover {
    color: #ff0000;
}

#SectionTitle { color: #0078d4; font-weight: bold; }
#PartitionInfoLabel { color: #888888; }

/* =======================================================
   标签弹窗 (TagPopup)
   ======================================================= */
#TagPopupContainer {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    border-radius: 6px;
}
#TagPopupHeader { color: #888888; border-bottom: 1px solid #eeeeee; }

#TagPopupButton {
    background-color: #f5f5f5;
    border: 1px solid #eeeeee;
    color: #333333;
}
#TagPopupButton:hover {
    background-color: #e6f7ff;
    border: 1px solid #1890ff;
}
#TagPopupButton:checked {
    background-color: #1890ff;
    color: #ffffff;
}

#TagCreateButton {
    background-color: #f0f9ff;
    color: #1890ff;
    border: 1px dashed #1890ff;
}
#TagCreateButton:hover {
    background-color: #1890ff;
    color: white;
}

/* =======================================================
   其他
   ======================================================= */
QPushButton {
    background-color: #ffffff;
    border: 1px solid #d9d9d9;
    color: #333333;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #f5f5f5;
    border-color: #0078d4;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background: #f3f3f3;
}
QScrollBar::handle {
    background: #c1c1c1;
    border-radius: 4px;
}
QScrollBar::handle:hover {
    background: #a8a8a8;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #cccccc;
}
QMenu::item:selected {
    background-color: #e6f7ff;
    color: #000000;
}
"""