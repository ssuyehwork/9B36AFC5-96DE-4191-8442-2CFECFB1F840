# -*- coding: utf-8 -*-
import logging
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QToolButton, QMenu, QAction, QDockWidget, QStylePainter, QStyleOption, QStyle
from PyQt5.QtCore import Qt

# 配置日志
log = logging.getLogger("CustomDock")

class CustomDockTitleBar(QWidget):
    def __init__(self, title, dock_widget, main_window, parent=None):
        super().__init__(parent)
        self.dock = dock_widget
        self.mw = main_window 
        
        self.setFixedHeight(38) # 增加高度，避免被视觉挤压
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("CustomDockTitleBar")  # 关键：设置对象名以确保样式表生效
        
        # 关键修复：设置显式的背景色，作为明显的拖拽手柄
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 5, 6) # 增加垂直内边距
        layout.setSpacing(0)
        
        self.label = QLabel(title)
        self.label.setObjectName("customDockLabel")
        layout.addWidget(self.label)
        
        layout.addStretch()
        
        self.btn_menu = QToolButton()
        self.btn_menu.setObjectName("customDockMenuButton")
        self.btn_menu.setText("≡")
        self.btn_menu.setFixedSize(24, 24)
        self.btn_menu.setCursor(Qt.PointingHandCursor)
        self.btn_menu.setPopupMode(QToolButton.InstantPopup)
        self.btn_menu.clicked.connect(self.show_menu)
        
        layout.addWidget(self.btn_menu)

    def paintEvent(self, event):
        """强制渲染 QSS 背景色，解决自定义 QWidget 背景不生效的问题"""
        opt = QStyleOption()
        opt.initFrom(self)
        p = QStylePainter(self)
        p.drawPrimitive(QStyle.PE_Widget, opt)
        super().paintEvent(event)

    def show_menu(self):
        log.info(f"🍔 点击了 [{self.label.text()}] 的菜单按钮")
        menu = QMenu(self)
        
        # 查找所有 Dock
        docks = self.mw.findChildren(QDockWidget)
        log.info(f"🔍 查找到 {len(docks)} 个面板: {[d.windowTitle() for d in docks]}")
        
        if not docks:
            log.warning("⚠️ 没有找到任何 Dock 面板！")
            
        for dock in docks:
            title = dock.windowTitle()
            if not title: continue
            
            action = QAction(title, menu)
            action.setCheckable(True)
            action.setChecked(dock.isVisible())
            # 使用闭包防止变量污染
            action.triggered.connect(lambda checked, d=dock: self.toggle_dock(d, checked))
            menu.addAction(action)
            
        menu.exec_(self.btn_menu.mapToGlobal(self.btn_menu.rect().bottomLeft()))

    def toggle_dock(self, dock, visible):
        log.info(f"🔄 切换面板 [{dock.windowTitle()}] 可见性 -> {visible}")
        dock.setVisible(visible)