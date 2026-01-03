# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication, QStyle
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal

class TrayManager(QSystemTrayIcon):
    """系统托盘管理器"""
    request_show_quick_panel = pyqtSignal()
    request_quit = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # TODO: Replace with logo.svg once it's available.
        # Using a standard application icon as a placeholder.
        app_icon = QApplication.style().standardIcon(QStyle.SP_ApplicationIcon)
        self.setIcon(app_icon)

        self.setToolTip("Clipboard Pro")

        # 创建菜单
        menu = QMenu()

        show_action = QAction("显示/隐藏 快速面板", self)
        show_action.triggered.connect(self.request_show_quick_panel.emit)
        menu.addAction(show_action)

        menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.request_quit.emit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

        # 连接托盘图标的激活事件 (例如单击)
        self.activated.connect(self.on_activated)

    def on_activated(self, reason):
        """处理托盘图标的激活事件"""
        # 如果是单击或双击，则触发显示/隐藏面板的信号
        if reason in (self.Trigger, self.DoubleClick):
            self.request_show_quick_panel.emit()
