# -*- coding: utf-8 -*-
import sys
import os
import ctypes
from ctypes import wintypes
import time
import datetime
import subprocess
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QListWidget, QLineEdit,
                             QListWidgetItem, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
                             QPushButton, QStyle, QAction, QSplitter, QGraphicsDropShadowEffect, QLabel,
                             QAbstractItemView)
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QSettings, QUrl, QMimeData
from PyQt5.QtGui import QImage, QColor, QCursor

# Import the new dialog
from ui.dialog_new_idea import NewIdeaDialog

# =================================================================================
#   Win32 API 定义
# =================================================================================
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_V = 0x56

# SetWindowPos Flags
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_FLAGS = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE

class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),      
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT)
    ]

user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
user32.GetGUIThreadInfo.restype = wintypes.BOOL
user32.SetFocus.argtypes = [wintypes.HWND]
user32.SetFocus.restype = wintypes.HWND
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]

# =================================================================================
#   日志系统
# =================================================================================
def log(message):
    try: print(message, flush=True)
    except: pass

# =================================================================================
#   数据库模拟
# =================================================================================
try:
    from data.database import DBManager
    from services.clipboard import ClipboardManager
except ImportError:
    class DBManager:
        def get_items(self, **kwargs): return []
        def get_partitions_tree(self): return []
    class ClipboardManager:
        def __init__(self, db_manager): pass
        def process_clipboard(self, mime_data): pass

# =================================================================================
#   样式表
# =================================================================================
DARK_STYLESHEET = """
QWidget#Container {
    background-color: #2E2E2E;
    border: 1px solid #444; 
    border-radius: 8px;    
}
QWidget {
    color: #F0F0F0;
    font-family: "Microsoft YaHei", "Segoe UI Emoji";
    font-size: 14px;
}

/* 标题栏文字样式 */
QLabel#TitleLabel {
    color: #AAAAAA;
    font-weight: bold;
    font-size: 13px;
    padding-left: 5px;
}

QListWidget, QTreeWidget {
    border: none;
    background-color: #2E2E2E;
    alternate-background-color: #383838;
    outline: none;
}
QListWidget::item { padding: 8px; border: none; }
QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #4D79C4; color: #FFFFFF;
}
QListWidget::item:hover { background-color: #444444; }

QSplitter::handle { background-color: #444; width: 2px; }
QSplitter::handle:hover { background-color: #4D79C4; }

QLineEdit {
    background-color: #3C3C3C;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px;
    font-size: 16px;
}

/* 通用工具栏按钮 */
QPushButton#ToolButton, QPushButton#MinButton, QPushButton#CloseButton, QPushButton#PinButton, QPushButton#MaxButton { 
    background-color: transparent; 
    border-radius: 4px; 
    padding: 0px;  
    font-size: 16px;
    font-weight: bold;
    text-align: center;
}

QPushButton#ToolButton:hover, QPushButton#MinButton:hover, QPushButton#MaxButton:hover { background-color: #444; }
QPushButton#ToolButton:checked, QPushButton#MaxButton:checked { background-color: #555; border: 1px solid #666; }

QPushButton#CloseButton:hover { background-color: #E81123; color: white; }

/* 置顶按钮特殊状态 */
QPushButton#PinButton:hover { background-color: #444; }
QPushButton#PinButton:checked { background-color: #0078D4; color: white; border: 1px solid #005A9E; }
"""

class MainWindow(QWidget):
    RESIZE_MARGIN = 18 

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.settings = QSettings("MyTools", "ClipboardPro")
        
        self.m_drag = False
        self.m_DragPosition = QPoint()
        self.resize_area = None
        
        self._is_pinned = False
        self.last_active_hwnd = None
        self.last_focus_hwnd = None
        self.last_thread_id = None
        self.my_hwnd = None
        self.main_window_instance = None # 持有主窗口实例
        
        # --- Clipboard Manager ---
        self.cm = ClipboardManager(self.db)
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_changed)
        self.cm.data_captured.connect(self._update_list)
        self._processing_clipboard = False
        
        self._init_ui()
        self._setup_shortcuts()  # Bind shortcuts
        self._restore_window_state()
        
        self.setMouseTracking(True)
        self.container.setMouseTracking(True)
        
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._monitor_foreground_window)
        self.monitor_timer.start(200)

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._update_list)
        
        self.search_box.textChanged.connect(self._on_search_text_changed)
        self.list_widget.itemActivated.connect(self._on_item_activated)
        self.partition_tree.currentItemChanged.connect(self._on_partition_selection_changed)
        
        self.clear_action.triggered.connect(self.search_box.clear)
        self.search_box.textChanged.connect(lambda text: self.clear_action.setVisible(bool(text)))
        self.clear_action.setVisible(False)
        
        # 按钮信号连接
        self.btn_stay_top.clicked.connect(self._toggle_stay_on_top)
        self.btn_toggle_side.clicked.connect(self._toggle_partition_panel)
        self.btn_open_full.clicked.connect(self._launch_main_app) # 连接启动功能
        self.btn_minimize.clicked.connect(self.showMinimized) 
        self.btn_close.clicked.connect(self.close)
        
        self._update_partition_tree()
        self._update_list()
        
        # 如果数据库为空，则添加调试数据
        if not self.db.get_items(limit=1):
            self._add_debug_test_item()

    def quick_add_idea(self, text):
        """从悬浮球快速添加文本到数据库"""
        log(f"💡 从悬浮球接收到快速添加请求: {text}")
        self.db.add_item(text, item_type='text')
        self._update_list() # 添加后刷新列表

    def new_idea(self):
        """弹出'新建灵感'对话框，并处理结果"""
        log("💡 '新建灵感' 被触发，正在打开对话框...")
        
        # 确保快速面板可见，否则对话框可能无法正确显示或成为焦点
        self.show()
        self.activateWindow()
        
        dialog = NewIdeaDialog(self)
        
        # 以模态方式执行对话框
        if dialog.exec_(): # exec_() for PyQt5
            idea_text = dialog.get_idea_text()
            if idea_text:
                log(f"✅ 对话框被接受，保存新灵感: '{idea_text[:50]}...'")
                # 使用现有的方法添加 item
                self.db.add_item(idea_text, item_type='text')
                # 刷新列表以显示新项目
                self._update_list()
                
                # 可选：将新项目滚动到视野中并选中
                if self.list_widget.count() > 0:
                    self.list_widget.setCurrentRow(0)
            else:
                log("🟡 对话框被接受，但内容为空，不执行任何操作。")
        else:
            log("❌ 对话框被取消。")

    def _init_ui(self):
        self.setWindowTitle("Clipboard Pro")
        self.resize(830, 630)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(15, 15, 15, 15) 
        
        self.container = QWidget()
        self.container.setObjectName("Container")
        self.root_layout.addWidget(self.container)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.container.setGraphicsEffect(shadow)
        
        self.setStyleSheet(DARK_STYLESHEET)
        
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        
        # --- Title Bar ---
        title_bar_layout = QHBoxLayout()
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        title_bar_layout.setSpacing(5)
        
        self.title_label = QLabel("Clipboard Pro")
        self.title_label.setObjectName("TitleLabel")
        title_bar_layout.addWidget(self.title_label)
        
        title_bar_layout.addStretch()
        
        # --- 按钮创建区 ---
        
        # 1. 保持置顶 (Pin)
        self.btn_stay_top = QPushButton("📌", self)
        self.btn_stay_top.setObjectName("PinButton")
        self.btn_stay_top.setToolTip("保持置顶")
        self.btn_stay_top.setCheckable(True)
        self.btn_stay_top.setFixedSize(32, 32)

        # 2. 侧边栏开关 (Eye)
        self.btn_toggle_side = QPushButton("👁️", self)
        self.btn_toggle_side.setObjectName("ToolButton")
        self.btn_toggle_side.setToolTip("显示/隐藏侧边栏")
        self.btn_toggle_side.setFixedSize(32, 32)
        
        # 3. 启动完整界面 (Open Main)
        self.btn_open_full = QPushButton(self)
        self.btn_open_full.setObjectName("MaxButton")
        self.btn_open_full.setToolTip("打开主程序界面")
        self.btn_open_full.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))
        self.btn_open_full.setFixedSize(32, 32)

        # 4. 最小化 (Minimize)
        self.btn_minimize = QPushButton("—", self)
        self.btn_minimize.setObjectName("MinButton")
        self.btn_minimize.setToolTip("最小化")
        self.btn_minimize.setFixedSize(32, 32)
        
        # 5. 关闭 (Close)
        self.btn_close = QPushButton(self)
        self.btn_close.setObjectName("CloseButton")
        self.btn_close.setToolTip("关闭")
        self.btn_close.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.btn_close.setFixedSize(32, 32)
        
        # 添加到布局
        title_bar_layout.addWidget(self.btn_stay_top)
        title_bar_layout.addWidget(self.btn_toggle_side)
        title_bar_layout.addWidget(self.btn_open_full) # 新增
        title_bar_layout.addWidget(self.btn_minimize)
        title_bar_layout.addWidget(self.btn_close)
        
        self.main_layout.addLayout(title_bar_layout)
        
        # --- Search Bar ---
        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("搜索剪贴板历史...")
        self.clear_action = QAction(self)
        self.clear_action.setIcon(self.style().standardIcon(QStyle.SP_DialogCloseButton))
        self.search_box.addAction(self.clear_action, QLineEdit.TrailingPosition)
        
        self.main_layout.addWidget(self.search_box)
        
        # --- Splitter Content ---
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(4)
        
        self.list_widget = QListWidget()
        self.list_widget.setFocusPolicy(Qt.StrongFocus)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)  # Enable multi-selection
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_list_context_menu)

        self.partition_tree = QTreeWidget()
        self.partition_tree.setHeaderHidden(True)
        self.partition_tree.setFocusPolicy(Qt.NoFocus)
        self.partition_tree.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.partition_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.splitter.addWidget(self.list_widget)
        self.splitter.addWidget(self.partition_tree)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([550, 150])
        
        content_layout.addWidget(self.splitter)
        self.main_layout.addWidget(content_widget)

    # --- Launch Main App Logic ---
    def _launch_main_app(self):
        """创建并显示主数据管理窗口"""
        try:
            if self.main_window_instance and self.main_window_instance.isVisible():
                self.main_window_instance.activateWindow()
                self.main_window_instance.raise_()
            else:
                from ui.main_window import MainWindow
                
                # 创建并持有实例
                self.main_window_instance = MainWindow()
                self.main_window_instance.show()
                
                # 居中显示
                screen_geo = QApplication.desktop().screenGeometry()
                window_geo = self.main_window_instance.geometry()
                self.main_window_instance.move(
                    (screen_geo.width() - window_geo.width()) // 2,
                    (screen_geo.height() - window_geo.height()) // 2
                )

        except Exception as e:
            log(f"❌ 启动主窗口失败: {e}")

    # --- Restore & Save State ---
    def _restore_window_state(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            screen_geo = QApplication.desktop().screenGeometry()
            win_geo = self.geometry()
            x = (screen_geo.width() - win_geo.width()) // 2
            y = (screen_geo.height() - win_geo.height()) // 2
            self.move(x, y)
        splitter_state = self.settings.value("splitter_state")
        if splitter_state: self.splitter.restoreState(splitter_state)

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter_state", self.splitter.saveState())
        super().closeEvent(event)

    # --- Mouse Logic ---
    def _get_resize_area(self, pos):
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = self.RESIZE_MARGIN
        areas = []
        if x < m: areas.append('left')
        elif x > w - m: areas.append('right')
        if y < m: areas.append('top')
        elif y > h - m: areas.append('bottom')
        return areas

    def _set_cursor_shape(self, areas):
        if not areas: self.setCursor(Qt.ArrowCursor); return
        if 'left' in areas and 'top' in areas: self.setCursor(Qt.SizeFDiagCursor)
        elif 'right' in areas and 'bottom' in areas: self.setCursor(Qt.SizeFDiagCursor)
        elif 'left' in areas and 'bottom' in areas: self.setCursor(Qt.SizeBDiagCursor)
        elif 'right' in areas and 'top' in areas: self.setCursor(Qt.SizeBDiagCursor)
        elif 'left' in areas or 'right' in areas: self.setCursor(Qt.SizeHorCursor)
        elif 'top' in areas or 'bottom' in areas: self.setCursor(Qt.SizeVerCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            areas = self._get_resize_area(event.pos())
            if areas:
                self.resize_area = areas
                self.m_drag = False
            else:
                self.resize_area = None
                self.m_drag = True
                self.m_DragPosition = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.NoButton:
            areas = self._get_resize_area(event.pos())
            self._set_cursor_shape(areas)
            event.accept()
            return
        if event.buttons() == Qt.LeftButton:
            if self.resize_area:
                global_pos = event.globalPos()
                rect = self.geometry()
                if 'left' in self.resize_area:
                    new_w = rect.right() - global_pos.x()
                    if new_w > 100: rect.setLeft(global_pos.x())
                elif 'right' in self.resize_area:
                    new_w = global_pos.x() - rect.left()
                    if new_w > 100: rect.setWidth(new_w)
                if 'top' in self.resize_area:
                    new_h = rect.bottom() - global_pos.y()
                    if new_h > 100: rect.setTop(global_pos.y())
                elif 'bottom' in self.resize_area:
                    new_h = global_pos.y() - rect.top()
                    if new_h > 100: rect.setHeight(new_h)
                self.setGeometry(rect)
                event.accept()
            elif self.m_drag:
                self.move(event.globalPos() - self.m_DragPosition)
                event.accept()

    def mouseReleaseEvent(self, event):
        self.m_drag = False
        self.resize_area = None
        self.setCursor(Qt.ArrowCursor)

    # --- Core Logic ---
    def showEvent(self, event):
        if not self.my_hwnd: self.my_hwnd = int(self.winId())
        super().showEvent(event)

    def _monitor_foreground_window(self):
        current_hwnd = user32.GetForegroundWindow()
        if current_hwnd == 0 or current_hwnd == self.my_hwnd: return
        if current_hwnd != self.last_active_hwnd:
            self.last_active_hwnd = current_hwnd
            self.last_thread_id = user32.GetWindowThreadProcessId(current_hwnd, None)
            self.last_focus_hwnd = None
            curr_thread = kernel32.GetCurrentThreadId()
            attached = False
            if curr_thread != self.last_thread_id:
                attached = user32.AttachThreadInput(curr_thread, self.last_thread_id, True)
            try:
                gui_info = GUITHREADINFO()
                gui_info.cbSize = ctypes.sizeof(GUITHREADINFO)
                if user32.GetGUIThreadInfo(self.last_thread_id, ctypes.byref(gui_info)):
                    self.last_focus_hwnd = gui_info.hwndFocus or gui_info.hwndActive
            except: pass
            finally:
                if attached: user32.AttachThreadInput(curr_thread, self.last_thread_id, False)

    def _on_search_text_changed(self): self.search_timer.start(300)

    def _update_list(self):
        search_text = self.search_box.text()
        partition_filter = None
        date_modify_filter = None # 新增变量
        current_partition = self.partition_tree.currentItem()
        if current_partition:
            partition_data = current_partition.data(0, Qt.UserRole)
            if partition_data:
                if partition_data['type'] == 'today':
                    date_modify_filter = '今日'
                    # partition_filter 保持为 None
                elif partition_data['type'] != 'all':
                    partition_filter = partition_data
        # 1. 从数据库获取未经过滤的数据
        all_items = self.db.get_items(partition_filter=partition_filter, date_modify_filter=date_modify_filter, limit=None)
        
        # 2. 在内存中进行搜索过滤
        if search_text:
            search_text_lower = search_text.lower()
            filtered_items = []
            for item in all_items:
                content_match = search_text_lower in getattr(item, 'content', '').lower()
                note_match = search_text_lower in getattr(item, 'note', '').lower()
                if content_match or note_match:
                    filtered_items.append(item)
            items = filtered_items
        else:
            items = all_items

        self.list_widget.clear()
        for item in items:
            display_text = self._get_content_display(item)
            list_item = QListWidgetItem(display_text)
            list_item.setData(Qt.UserRole, item)
            if getattr(item, 'content', ''):
                list_item.setToolTip(str(item.content)[:500])
            self.list_widget.addItem(list_item)
        if self.list_widget.count() > 0: self.list_widget.setCurrentRow(0)

    def _get_content_display(self, item):
        if getattr(item, 'item_type', '') == 'file' and getattr(item, 'file_path', ''):
            return os.path.basename(item.file_path)
        elif getattr(item, 'item_type', '') == 'url' and getattr(item, 'url_domain', None):
            return f"[{item.url_domain}] {item.url_title or ''}"
        elif getattr(item, 'item_type', '') == 'image':
            return "[图片] " + (os.path.basename(item.image_path) if getattr(item, 'image_path', None) else "")
        else:
            return getattr(item, 'content', '').replace('\n', ' ').replace('\r', '').strip()[:150]

    def _create_color_icon(self, color_str):
        from PyQt5.QtGui import QPixmap, QPainter, QIcon
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(color_str or "#808080"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(2, 2, 12, 12, 4, 4)
        painter.end()
        return QIcon(pixmap)

    def _update_partition_tree(self):
        current_selection = self.partition_tree.currentItem().data(0, Qt.UserRole) if self.partition_tree.currentItem() else None
        self.partition_tree.clear()
        
        counts = self.db.get_partition_item_counts()
        partition_counts = counts.get('partitions', {})

        # -- 添加静态项 --
        static_items = [
            ("全部数据", {'type': 'all', 'id': -1}, QStyle.SP_DirHomeIcon, counts.get('total', 0)),
            ("今日数据", {'type': 'today', 'id': -5}, QStyle.SP_FileDialogDetailedView, counts.get('today_modified', 0)),
        ]
        
        for name, data, icon, count in static_items:
            item = QTreeWidgetItem(self.partition_tree, [f"{name} ({count})"])
            item.setData(0, Qt.UserRole, data)
            item.setIcon(0, self.style().standardIcon(icon))
        
        # -- 递归添加用户分区 --
        top_level_partitions = self.db.get_partitions_tree()
        self._add_partition_recursive(top_level_partitions, self.partition_tree, partition_counts)

        self.partition_tree.expandAll()
        
        # 恢复之前的选择
        if current_selection:
            it = QTreeWidgetItemIterator(self.partition_tree)
            while it.value():
                item = it.value()
                item_data = item.data(0, Qt.UserRole)
                if item_data and item_data.get('id') == current_selection.get('id') and item_data.get('type') == current_selection.get('type'):
                    self.partition_tree.setCurrentItem(item)
                    break
                it += 1
        else:
            if self.partition_tree.topLevelItemCount() > 0:
                self.partition_tree.setCurrentItem(self.partition_tree.topLevelItem(0))

    def _add_partition_recursive(self, partitions, parent_item, partition_counts):
        for partition in partitions:
            count = partition_counts.get(partition.id, 0)
            item = QTreeWidgetItem(parent_item, [f"{partition.name} ({count})"])
            item.setData(0, Qt.UserRole, {'type': 'partition', 'id': partition.id, 'color': partition.color})
            item.setIcon(0, self._create_color_icon(partition.color))
            
            if partition.children:
                self._add_partition_recursive(partition.children, item, partition_counts)

    def _on_partition_selection_changed(self, c, p): self._update_list()
    def _toggle_partition_panel(self): self.partition_tree.setVisible(not self.partition_tree.isVisible())
    
    def _toggle_stay_on_top(self):
        self._is_pinned = self.btn_stay_top.isChecked()
        hwnd = int(self.winId())
        if self._is_pinned:
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_FLAGS)
        else:
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_FLAGS)

    def _on_item_activated(self, item):
        db_item = item.data(Qt.UserRole)
        if not db_item: return
        try:
            clipboard = QApplication.clipboard()
            
            # 1. 处理图片
            if getattr(db_item, 'item_type', '') == 'image' and getattr(db_item, 'data_blob', None):
                image = QImage()
                image.loadFromData(db_item.data_blob)
                clipboard.setImage(image)
            
            # 2. 处理文件：构建 URI 列表
            elif getattr(db_item, 'item_type', '') == 'file' and getattr(db_item, 'file_path', ''):
                mime_data = QMimeData()
                urls = [QUrl.fromLocalFile(p) for p in db_item.file_path.split(';') if p]
                mime_data.setUrls(urls)
                clipboard.setMimeData(mime_data)
                
            # 3. 处理普通文本/链接
            else:
                clipboard.setText(db_item.content)
            
            self._paste_ditto_style()
        except Exception as e: log(f"❌ 操作失败: {e}")

    def _paste_ditto_style(self):
        target_win = self.last_active_hwnd
        target_focus = self.last_focus_hwnd
        target_thread = self.last_thread_id
        if not target_win or not user32.IsWindow(target_win): return
        curr_thread = kernel32.GetCurrentThreadId()
        attached = False
        if target_thread and curr_thread != target_thread:
            attached = user32.AttachThreadInput(curr_thread, target_thread, True)
        try:
            if user32.IsIconic(target_win): user32.ShowWindow(target_win, 9)
            user32.SetForegroundWindow(target_win)
            if target_focus and user32.IsWindow(target_focus): user32.SetFocus(target_focus)
            time.sleep(0.1)
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(VK_V, 0, 0, 0)
            user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        except Exception as e: log(f"❌ 粘贴异常: {e}")
        finally:
            if attached: user32.AttachThreadInput(curr_thread, target_thread, False)

    def on_clipboard_changed(self):
        if self._processing_clipboard:
            return
        self._processing_clipboard = True
        try:
            mime = self.clipboard.mimeData()
            # quick.py 默认不与特定分区关联，所以传入 None
            self.cm.process_clipboard(mime, None)
        finally:
            self._processing_clipboard = False

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape: self.close()
        elif key in (Qt.Key_Up, Qt.Key_Down):
            if not self.list_widget.hasFocus():
                self.list_widget.setFocus()
                QApplication.sendEvent(self.list_widget, event)
        else: super().keyPressEvent(event)

    def _show_list_context_menu(self, pos):
        """Build and show the enhanced context menu."""
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return

        menu = QMenu(self)
        
        # Single-item actions
        if len(selected_items) == 1:
            item_data = selected_items[0].data(Qt.UserRole)
            menu.addAction("👁️ 预览 (Space)", self._do_preview)
            menu.addAction("📋 复制内容", lambda: self._copy_item_content(item_data))
            menu.addSeparator()

        # Batch actions
        menu.addAction("⭐ 收藏选中项", self._do_batch_toggle_favorite)
        menu.addAction("📌 置顶选中项", self._do_batch_toggle_pin)
        menu.addAction("🔒 锁定/解锁选中项", self._do_batch_toggle_lock)
        
        # Move to partition submenu
        move_menu = menu.addMenu("📂 移动到...")
        partitions = self.db.get_partitions_tree()
        self._add_partitions_to_menu(partitions, move_menu)
        
        menu.addSeparator()
        menu.addAction("🗑️ 删除选中项 (Del)", self._do_batch_delete)

        menu.exec_(self.list_widget.mapToGlobal(pos))

    def _add_partitions_to_menu(self, partitions, parent_menu):
        """Recursively add partitions to the move menu."""
        for p in partitions:
            action = parent_menu.addAction(p.name)
            action.triggered.connect(lambda _, pid=p.id: self._move_selection_to_partition(pid))
            if p.children:
                child_menu = QMenu(p.name, self)
                parent_menu.addMenu(child_menu)
                self._add_partitions_to_menu(p.children, child_menu)

    def _move_selection_to_partition(self, partition_id):
        """Move selected items to a specific partition."""
        ids = self._get_selected_ids()
        if not ids: return
        deletable_ids = [id for id in ids if not self.db.get_idea(id).is_locked]
        if not deletable_ids: return
        for id in deletable_ids:
            self.db.move_category(id, partition_id)
        self._update_list()
        self._update_partition_tree()

    def _do_preview(self):
        """Preview the currently selected item."""
        if len(self.list_widget.selectedItems()) == 1:
            # Assuming a preview service exists, similar to main_window
            pass

    def _copy_item_content(self, item_data):
        """Copy content of a single item to clipboard."""
        if not item_data: return
        content_to_copy = getattr(item_data, 'content', "")
        QApplication.clipboard().setText(content_to_copy)


    # --- Batch Operation Methods ---
    def _get_selected_ids(self):
        """Helper to get all selected item IDs."""
        selected_items = self.list_widget.selectedItems()
        return [item.data(Qt.UserRole).id for item in selected_items if item.data(Qt.UserRole)]

    def _do_batch_toggle_favorite(self):
        """Batch toggle favorite status for selected items."""
        ids = self._get_selected_ids()
        if not ids: return
        # A simple toggle: if any are not favorite, make all favorite. Otherwise, unfavorite all.
        is_favorite = any(not self.db.get_idea(id).is_favorite for id in ids)
        for id in ids:
            self.db.set_favorite(id, is_favorite)
        self._update_list()

    def _do_batch_toggle_pin(self):
        """Batch toggle pin status for selected items."""
        ids = self._get_selected_ids()
        if not ids: return
        is_pinned = any(not self.db.get_idea(id).is_pinned for id in ids)
        for id in ids:
            self.db.toggle_field(id, 'is_pinned') # Assuming toggle_field handles this
        self._update_list()

    def _do_batch_toggle_lock(self):
        """Batch toggle lock status for selected items."""
        ids = self._get_selected_ids()
        if not ids: return
        # If any are unlocked, lock all. Otherwise, unlock all.
        is_locked = any(not self.db.get_idea(id).is_locked for id in ids)
        for id in ids:
            self.db.set_locked([id], is_locked)
        self._update_list()

    def _do_batch_delete(self):
        """Batch move selected items to trash."""
        ids = self._get_selected_ids()
        if not ids: return
        # Filter out locked items
        deletable_ids = [id for id in ids if not self.db.get_idea(id).is_locked]
        if not deletable_ids: return
        for id in deletable_ids:
            self.db.set_deleted(id, True)
        self._update_list()
        self._update_partition_tree()

    def _setup_shortcuts(self):
        """Setup global shortcuts for the window."""
        QShortcut(QKeySequence("Ctrl+E"), self, self._do_batch_toggle_favorite)
        QShortcut(QKeySequence("Ctrl+S"), self, self._do_batch_toggle_lock)
        QShortcut(QKeySequence("Del"), self, self._do_batch_delete)
        QShortcut(QKeySequence("Ctrl+A"), self, self.list_widget.selectAll)
        # Assuming a preview function exists or will be added
        # QShortcut(QKeySequence(Qt.Key_Space), self, self._do_preview)

    def _add_debug_test_item(self):
        """仅在数据库为空时，用于填充一些示例数据"""
        for i in range(20):
            item = QListWidgetItem(f"测试数据 {i+1}")
            mock_data = type('obj', (object,), {'item_type': 'text', 'content': f'Content {i}'})
            item.setData(Qt.UserRole, mock_data)
            self.list_widget.addItem(item)