# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal

class TrayManager(QSystemTrayIcon):
    """系统托盘管理器"""
    request_show_quick_panel = pyqtSignal()
    request_quit = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # 设置图标 (这里使用一个Qt内置的标准图标作为占位符)
        # 理想情况下, 这里应该使用一个 .ico 或 .png 文件
        self.setIcon(QIcon.fromTheme("utilities-terminal"))

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
