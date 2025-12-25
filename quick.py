# -*- coding: utf-8 -*-
import sys
import os
import ctypes
from ctypes import wintypes
import time
import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QListWidget, QLineEdit, 
                             QListWidgetItem, QHBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QPushButton, QStyle, QAction, QSplitter, QGraphicsDropShadowEffect, QLabel)
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QSettings
from PyQt5.QtGui import QImage, QColor, QCursor

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
except ImportError:
    class DBManager:
        def get_items(self, **kwargs): return []
        def get_partitions_tree(self): return []

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

/* 通用工具栏按钮 (包含侧边栏按钮) */
QPushButton#ToolButton { 
    background-color: transparent; 
    border-radius: 4px; 
    padding: 4px;
    font-size: 16px; /* 稍微调大字体以显示Emoji */
}
QPushButton#ToolButton:hover { background-color: #444; }
QPushButton#ToolButton:checked { background-color: #555; border: 1px solid #666; }

QPushButton#CloseButton { background-color: transparent; border-radius: 4px; }
QPushButton#CloseButton:hover { background-color: #E81123; color: white; }

/* 置顶按钮 */
QPushButton#PinButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    font-size: 16px;
}
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
        
        self._init_ui()
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
        
        self.btn_stay_top.clicked.connect(self._toggle_stay_on_top)
        self.btn_toggle_side.clicked.connect(self._toggle_partition_panel)
        self.btn_close.clicked.connect(self.close)
        
        self._update_partition_tree()
        self._update_list()
        self._add_debug_test_item()

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
        
        # [修改] 侧边栏开关：图标改为 "👁️"
        self.btn_toggle_side = QPushButton("👁️", self)
        self.btn_toggle_side.setObjectName("ToolButton")
        self.btn_toggle_side.setToolTip("显示/隐藏侧边栏")
        self.btn_toggle_side.setFixedSize(32, 32)
        
        self.btn_stay_top = QPushButton("📌", self)
        self.btn_stay_top.setObjectName("PinButton")
        self.btn_stay_top.setToolTip("保持置顶")
        self.btn_stay_top.setCheckable(True)
        self.btn_stay_top.setFixedSize(32, 32)
        
        self.btn_close = QPushButton(self)
        self.btn_close.setObjectName("CloseButton")
        self.btn_close.setToolTip("关闭")
        self.btn_close.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.btn_close.setFixedSize(32, 32)
        
        title_bar_layout.addWidget(self.btn_toggle_side)
        title_bar_layout.addWidget(self.btn_stay_top)
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
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

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
        current_partition = self.partition_tree.currentItem()
        if current_partition:
            partition_data = current_partition.data(0, Qt.UserRole)
            if partition_data and partition_data['type'] != 'all':
                partition_filter = partition_data
        items = self.db.get_items(search=search_text, partition_filter=partition_filter, limit=100)
        self.list_widget.clear()
        self._add_debug_test_item()
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

    def _update_partition_tree(self):
        self.partition_tree.clear()
        all_items_node = QTreeWidgetItem(self.partition_tree, ["全部"])
        all_items_node.setData(0, Qt.UserRole, {'type': 'all', 'id': -1})
        top_level_partitions = self.db.get_partitions_tree()
        self._add_partition_recursive(top_level_partitions, self.partition_tree)
        self.partition_tree.expandAll()
        self.partition_tree.setCurrentItem(all_items_node)

    def _add_partition_recursive(self, partitions, parent_item):
        for partition in partitions:
            item = QTreeWidgetItem(parent_item, [partition.name])
            item.setData(0, Qt.UserRole, {'type': 'partition', 'id': partition.id})
            if partition.children: self._add_partition_recursive(partition.children, item)

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
            if getattr(db_item, 'item_type', '') == 'image' and getattr(db_item, 'data_blob', None):
                image = QImage()
                image.loadFromData(db_item.data_blob)
                clipboard.setImage(image)
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

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape: self.close()
        elif key in (Qt.Key_Up, Qt.Key_Down):
            if not self.list_widget.hasFocus():
                self.list_widget.setFocus()
                QApplication.sendEvent(self.list_widget, event)
        else: super().keyPressEvent(event)

    def _add_debug_test_item(self):
        if self.list_widget.count() == 0 and not self.db.get_items():
            for i in range(20):
                item = QListWidgetItem(f"测试数据 {i+1}")
                mock_data = type('obj', (object,), {'item_type': 'text', 'content': f'Content {i}'})
                item.setData(Qt.UserRole, mock_data)
                self.list_widget.addItem(item)

if __name__ == '__main__':
    log("🚀 程序启动 (Eye Icon Update)")
    app = QApplication(sys.argv)
    try: db_manager = DBManager()
    except: sys.exit(1)
    window = MainWindow(db_manager=db_manager) 
    window.show()
    sys.exit(app.exec_())
