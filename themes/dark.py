# -*- coding: utf-8 -*-
"""
深色主题样式表 - 极简现代版
去除多余装饰(三角形指示器)，优化间距，重构滚动条
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
    background-color: #2b2b2b;
    color: #e0e0e0;
}

QWidget:disabled {
    color: #6e6e6e;
}

QToolTip {
    background-color: #3f3f3f;
    color: #ffffff;
    border: 1px solid #555555;
    padding: 4px;
    border-radius: 4px;
}

/* =======================================================
   去除所有菜单指示器 (核心需求)
   ======================================================= */
QToolButton::menu-indicator, 
QPushButton::menu-indicator, 
QComboBox::drop-down {
    image: none;
    border: none;
    width: 0px;
    height: 0px;
    padding: 0px;
}

/* =======================================================
   主窗口容器
   ======================================================= */
#MainFrame {
    background-color: #1e1e1e;
    border: 1px solid #454545;
    border-radius: 8px;
}

/* =======================================================
   标题栏 (CustomTitleBar)
   ======================================================= */
CustomTitleBar {
    background-color: #252526;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    border-bottom: 1px solid #333333;
}

#WindowTitle {
    font-weight: bold;
    font-size: 14px;
    color: #cccccc;
    background-color: transparent;
    padding-left: 5px;
}

#TitleBarSeparator {
    color: #3e3e42;
    background-color: transparent;
}

/* 窗口控制按钮 - 移除内边距，确保图标居中 */
#WindowControlButton, #WindowCloseButton {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    color: #aaaaaa;
    padding: 0px; /* 核心修复：移除不合理的内边距 */
    margin: 0px;
}
#WindowControlButton:hover { background-color: #3e3e42; color: #ffffff; }
#WindowCloseButton:hover { background-color: #e81123; color: #ffffff; }

/* 工具栏按钮 - 移除内边距 */
#ToolBarButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    color: #cccccc;
    padding: 0px; /* 核心修复：移除内边距 */
    margin: 0px;
}
#ToolBarButton:hover { background-color: #3e3e42; border-color: #555555; }
#ToolBarButton:checked { background-color: #264f78; border-color: #555555; color: #ffffff; }

/* 搜索框 */
#ToolbarSearchBar {
    background-color: #3c3c3c;
    border: 1px solid #3c3c3c;
    border-radius: 12px;
    padding: 2px 10px;
    color: #f0f0f0;
    selection-background-color: #264f78;
}
#ToolbarSearchBar:focus {
    border: 1px solid #007fd4;
    background-color: #252526;
}

/* 显示条数按钮 - 纯文字模式，无边框背景 */
#DisplayCountButton {
    background: transparent;
    color: #aaaaaa;
    border: none;
    padding: 4px 8px;
    text-align: center;
}
#DisplayCountButton:hover { 
    color: #ffffff; 
    background-color: #3e3e42;
    border-radius: 4px;
}

/* =======================================================
   滚动条重构 (极简现代风格)
   ======================================================= */
/* 垂直滚动条 */
QScrollBar:vertical {
    border: none;
    background: transparent; /* 透明轨道 */
    width: 6px; /* 极细宽度 */
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #424242; /* 深灰色滑块 */
    min-height: 30px;
    border-radius: 3px; /* 圆角 */
}
QScrollBar::handle:vertical:hover {
    background: #686868; /* 悬停变亮 */
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px; /* 移除上下箭头按钮 */
    background: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none; /* 点击轨道不跳转或无背景 */
}

/* 水平滚动条 */
QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 6px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #424242;
    min-width: 30px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover {
    background: #686868;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    background: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}

/* =======================================================
   Dock 面板框架
   ======================================================= */
QMainWindow::separator {
    background-color: #1e1e1e;
    width: 4px;
    height: 4px;
}
QMainWindow::separator:hover {
    background-color: #007fd4;
}

#CustomDockTitleBar {
    background-color: #252526;
    border-bottom: 1px solid #333333;
}
#customDockLabel {
    font-weight: bold;
    font-size: 13px;
    color: #cccccc;
    background: transparent;
}
#customDockMenuButton {
    background: transparent;
    border: none;
    color: #888888;
    padding: 0px;
}
#customDockMenuButton:hover { color: #ffffff; background-color: #3e3e42; border-radius: 3px; }

/* =======================================================
   主列表表格
   ======================================================= */
QTableWidget {
    background-color: #1e1e1e;
    gridline-color: transparent;
    border: none;
    selection-background-color: #094771;
    selection-color: #ffffff;
    alternate-background-color: #252526;
}
QTableWidget::item {
    padding: 4px;
    border: none;
}
QTableWidget::item:hover {
    background-color: #2a2d2e;
}
QTableWidget::item:selected {
    background-color: #37373d;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #252526;
    color: #cccccc;
    padding: 5px;
    border: none;
    border-right: 1px solid #333333;
    border-bottom: 1px solid #333333;
    font-weight: bold;
}
QTableCornerButton::section {
    background-color: #252526;
    border: none;
}

/* =======================================================
   左侧树形列表
   ======================================================= */
QTreeWidget {
    background-color: #252526;
    border: none;
}
QTreeWidget::item {
    padding: 6px;
    border-radius: 4px;
    margin-right: 8px;
}
QTreeWidget::item:hover {
    background-color: #2a2d2e;
}
QTreeWidget::item:selected {
    background-color: #37373d;
    color: #ffffff;
}

/* =======================================================
   其他控件
   ======================================================= */
#PreviewBox, #NoteInput, #TagInputWidget QLineEdit {
    background-color: #1e1e1e;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 6px;
    color: #cccccc;
}
#NoteInput:focus, #TagInputWidget QLineEdit:focus {
    border: 1px solid #007fd4;
    background-color: #000000;
}

#TagInputWidget {
    background-color: #1e1e1e;
    border: 1px solid #333333;
    border-radius: 6px;
}

/* 标签胶囊 */
#ChipsContainer QFrame {
    background-color: #333333;
    border-radius: 12px;
    color: #f0f0f0;
    border: 1px solid #454545;
}
#TagCloseButton {
    background: transparent;
    color: #aaaaaa;
    border-radius: 7px;
    font-weight: bold;
    padding: 0; 
    margin: 0;
}
#TagCloseButton:hover {
    background-color: #e81123;
    color: #ffffff;
}

#SectionTitle {
    color: #569cd6;
    font-weight: bold;
    font-size: 13px;
    margin-top: 5px;
}
#PartitionInfoLabel { color: #888888; font-size: 12px; }

#StatusLabel, #PageLabel { color: #888888; background: transparent; }

/* 通用按钮 (底部栏等) */
QPushButton {
    background-color: #333333;
    border: 1px solid #454545;
    color: #cccccc;
    border-radius: 4px;
    padding: 4px 10px;
}
QPushButton:hover {
    background-color: #3e3e42;
    border-color: #666666;
}
QPushButton:pressed {
    background-color: #1e1e1e;
}

/* 菜单 */
QMenu {
    background-color: #252526;
    border: 1px solid #454545;
    padding: 4px 0px;
}
QMenu::item {
    background: transparent;
    padding: 6px 30px 6px 10px;
    color: #cccccc;
}
QMenu::item:selected {
    background-color: #094771;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #454545;
    margin: 4px 0px;
}
"""