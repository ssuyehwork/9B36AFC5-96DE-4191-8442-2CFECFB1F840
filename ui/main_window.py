# -*- coding: utf-8 -*-
import logging
# -*- coding: utf-8 -*-
import logging
import ctypes
import os
from ctypes.wintypes import MSG
from datetime import datetime, time, timedelta
from collections import deque

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QDockWidget, QLabel, QPushButton, QFrame, 
                             QApplication, QShortcut, QSizeGrip, QMessageBox,
                             QAbstractItemView, QTableWidgetItem, QHeaderView, QMenu)
from PyQt5.QtCore import Qt, QPoint, QTimer, QSettings, QRect
from PyQt5.QtGui import QColor, QKeySequence, QImage
from sqlalchemy.orm import joinedload

# 核心逻辑
from data.database import DBManager, Partition
from services.clipboard import ClipboardManager
from core.shared import format_size, get_color_icon
from core.datetime_utils import get_date_label

# UI 组件
from ui.components import CustomTitleBar
from ui.custom_dock import CustomDockTitleBar
from ui.panel_filter import FilterPanel
from ui.panel_table import TablePanel
from ui.panel_detail import DetailPanel
from ui.panel_tags import TagPanel
from ui.panel_partition import PartitionPanel
from ui.dialogs import TagDialog, ColorDialog
from ui.context_menu import ContextMenuHandler
from ui.color_selector import ColorSelectorDialog
from ui.dialog_preview import PreviewDialog

import themes.dark
import themes.light
import platform

# 配置日志
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("MainWindow")

# Windows API
if platform.system() == "Windows":
    SetWindowPos = ctypes.windll.user32.SetWindowPos
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010
else:
    SetWindowPos = lambda *args: None
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        log.info("🚀 初始化 MainWindow...")
        self.setWindowTitle("印象记忆_Pro")
        
        screen_geo = QApplication.desktop().availableGeometry()
        screen_w, screen_h = screen_geo.width(), screen_geo.height()
        
        init_w = min(1200, int(screen_w * 0.9))
        init_h = min(700, int(screen_h * 0.9))
        self.resize(init_w, init_h)
        self.move((screen_w - init_w) // 2, (screen_h - init_h) // 2)
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        
        self.border_width = 8
        self.is_pinned = False
        
        self.edit_mode = False
        self.current_sort_mode = "manual"
        self.last_external_hwnd = None
        self.col_alignments = {} 
        self.current_item_id = None
        self.page = 1
        self.page_size = 100
        self.total_items = 0
        self.item_id_to_select_after_load = None
        
        # 剪贴板队列 + 防抖
        self._clipboard_queue = deque(maxlen=10)
        self._clipboard_timer = QTimer(self)
        self._clipboard_timer.setSingleShot(True)
        self._clipboard_timer.timeout.connect(self._process_clipboard_queue)

        self.cached_items = []
        self.cached_items_map = {}
        
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(500)
        self.save_timer.timeout.connect(self.save_window_state)
        
        self.focus_timer = QTimer()
        self.focus_timer.timeout.connect(self.track_active_window)
        self.focus_timer.start(200)
        
        self.db = DBManager()
        self.cm = ClipboardManager(self.db)
        self.cm.data_captured.connect(self.refresh_after_capture) 
        
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_event)
        
        self.setup_ui()
        self.menu_handler = ContextMenuHandler(self)
        self.setup_shortcuts()
        
        self.restore_window_state()
        self.load_data()
        
        log.info("✅ 主窗口启动完毕")

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.outer_layout = QVBoxLayout(self.central_widget)
        self.outer_layout.setContentsMargins(5, 5, 5, 5) 
        self.outer_layout.setSpacing(0)
        
        self.big_container = QFrame()
        self.big_container.setObjectName("MainFrame")
        self.outer_layout.addWidget(self.big_container)
        self.inner_layout = QVBoxLayout(self.big_container)
        self.inner_layout.setContentsMargins(0, 0, 0, 0)
        self.inner_layout.setSpacing(0)
        
        self.title_bar = CustomTitleBar(self)
        self.title_bar.refresh_clicked.connect(self.load_data)
        self.title_bar.theme_clicked.connect(self.toggle_theme)
        self.title_bar.search_changed.connect(self._apply_frontend_filters)
        self.title_bar.display_count_changed.connect(self.on_display_count_changed)
        self.title_bar.pin_clicked.connect(self.toggle_pin)
        self.title_bar.clean_clicked.connect(self.auto_clean)
        self.title_bar.mode_clicked.connect(self.toggle_edit_mode)
        self.title_bar.color_clicked.connect(self.toolbar_set_color)
        self.inner_layout.addWidget(self.title_bar)
        
        self.dock_container = QMainWindow()
        self.dock_container.setWindowFlags(Qt.Widget)
        self.dock_container.setDockOptions(
            QMainWindow.AllowNestedDocks | QMainWindow.AnimatedDocks | QMainWindow.GroupedDragging
        )
        self.dock_container.setCorner(Qt.TopLeftCorner, Qt.LeftDockWidgetArea)
        self.dock_container.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        self.dock_container.setCorner(Qt.TopRightCorner, Qt.RightDockWidgetArea)
        self.dock_container.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)
        self.inner_layout.addWidget(self.dock_container, 1) 
        
        self.dock_filter = QDockWidget("筛选器", self.dock_container)
        self.dock_filter.setObjectName("DockFilter")
        self.dock_filter.setTitleBarWidget(CustomDockTitleBar("筛选器", self.dock_filter, self.dock_container))
        self.dock_filter.setFeatures(QDockWidget.AllDockWidgetFeatures)
        self.dock_filter.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.filter_panel = FilterPanel() 
        self.filter_panel.filterChanged.connect(self._apply_frontend_filters)
        self.dock_filter.setWidget(self.filter_panel)
        self.dock_container.addDockWidget(Qt.LeftDockWidgetArea, self.dock_filter)
        
        self.dock_partition = QDockWidget("分区组", self.dock_container)
        self.dock_partition.setObjectName("DockPartition")
        self.dock_partition.setTitleBarWidget(CustomDockTitleBar("分区组", self.dock_partition, self.dock_container))
        self.dock_partition.setFeatures(QDockWidget.AllDockWidgetFeatures)
        self.dock_partition.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.partition_panel = PartitionPanel(self.db)
        self.partition_panel.partitionSelectionChanged.connect(lambda: self.load_data(reset_page=True))
        self.partition_panel.partitionsUpdated.connect(self.partition_panel.refresh_partitions)
        self.partition_panel.partitionsUpdated.connect(self.load_data)
        self.dock_partition.setWidget(self.partition_panel)
        self.dock_container.addDockWidget(Qt.LeftDockWidgetArea, self.dock_partition)

        self.dock_tags = QDockWidget("标签", self.dock_container)
        self.dock_tags.setObjectName("DockTags")
        self.dock_tags.setTitleBarWidget(CustomDockTitleBar("标签", self.dock_tags, self.dock_container))
        self.dock_tags.setFeatures(QDockWidget.AllDockWidgetFeatures)
        self.dock_tags.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.tag_panel = TagPanel()
        self.tag_panel.setEnabled(False)
        self.tag_panel.tags_committed.connect(self.on_tag_panel_commit_tags)
        self.tag_panel.tag_selected.connect(self.on_tag_selected)
        self.dock_tags.setWidget(self.tag_panel)
        self.dock_container.addDockWidget(Qt.LeftDockWidgetArea, self.dock_tags)
        
        self.dock_container.splitDockWidget(self.dock_filter, self.dock_partition, Qt.Horizontal)
        self.dock_container.splitDockWidget(self.dock_partition, self.dock_tags, Qt.Horizontal)

        self.dock_detail = QDockWidget("详细信息", self.dock_container)
        self.dock_detail.setObjectName("DockDetail")
        self.dock_detail.setTitleBarWidget(CustomDockTitleBar("详细信息", self.dock_detail, self.dock_container))
        self.dock_detail.setFeatures(QDockWidget.AllDockWidgetFeatures)
        self.dock_detail.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.detail_panel = DetailPanel() 
        self.detail_panel.update_note_signal.connect(self.save_note)
        self.detail_panel.tags_added_signal.connect(self.on_tags_added)
        self.detail_panel.remove_tag_signal.connect(self.remove_tag)
        self.dock_detail.setWidget(self.detail_panel)
        self.dock_container.addDockWidget(Qt.RightDockWidgetArea, self.dock_detail)
        
        self.table = TablePanel()
        from PyQt5.QtWidgets import QSizePolicy
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setMinimumWidth(300)
        self.table.horizontalHeader().customContextMenuRequested.connect(self.show_header_menu)
        self.table.horizontalHeader().sectionResized.connect(self.schedule_save_state)
        self.table.itemSelectionChanged.connect(self.update_detail_panel)
        self.table.itemDoubleClicked.connect(self.on_table_double_click)
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.reorder_signal.connect(self.reorder_items)
        self.dock_container.setCentralWidget(self.table)
        
        # Hide the detail panel by default as requested
        self.dock_detail.hide()
        
        self.filter_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.partition_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.tag_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.detail_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        
        self.dock_container.setMouseTracking(True)
        min_w = 230
        for dock in [self.dock_filter, self.dock_partition, self.dock_tags, self.dock_detail]:
            dock.setMinimumWidth(min_w)
            dock.setMaximumWidth(16777215)
        
        self.bottom_bar = QWidget()
        self.bottom_bar.setFixedHeight(32)
        bl = QHBoxLayout(self.bottom_bar)
        bl.setContentsMargins(10, 0, 10, 0)
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setObjectName("StatusLabel")
        bl.addWidget(self.lbl_status)
        bl.addStretch()

        self.btn_first = QPushButton("« 首页")
        self.btn_first.setFixedSize(80, 28)
        self.btn_prev = QPushButton("< 上一页")
        self.btn_prev.setFixedSize(80, 28)
        self.lbl_page = QLabel("1 / 1")
        self.lbl_page.setObjectName("PageLabel")
        self.btn_next = QPushButton("下一页 >")
        self.btn_next.setFixedSize(80, 28)
        self.btn_last = QPushButton("末页 »")
        self.btn_last.setFixedSize(80, 28)
        self.btn_first.clicked.connect(self.go_to_first_page)
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next.clicked.connect(self.next_page)
        self.btn_last.clicked.connect(self.go_to_last_page)
        bl.addWidget(self.btn_first)
        bl.addWidget(self.btn_prev)
        bl.addWidget(self.lbl_page)
        bl.addWidget(self.btn_next)
        bl.addWidget(self.btn_last)
        self.size_grip = QSizeGrip(self.bottom_bar)
        self.size_grip.setFixedSize(16, 16)
        bl.addWidget(self.size_grip, 0, Qt.AlignBottom | Qt.AlignRight)
        self.inner_layout.addWidget(self.bottom_bar)
        
        for dock in [self.dock_filter, self.dock_partition, self.dock_tags, self.dock_detail]:
            dock.dockLocationChanged.connect(self.schedule_save_state)
            dock.visibilityChanged.connect(self.handle_dock_visibility_changed)
        
        self.table.horizontalHeader().sectionResized.connect(self.schedule_save_state)
        self.table.horizontalHeader().sectionMoved.connect(self.schedule_save_state)
        QTimer.singleShot(100, self.connect_splitters)

        self.preview_dlg = None
        self.table.installEventFilter(self)
        log.info("✅ UI初始化完成")

    def connect_splitters(self):
        log.debug("连接Dock容器中的QSplitter信号...")
        from PyQt5.QtWidgets import QSplitter
        splitters = self.dock_container.findChildren(QSplitter)
        for splitter in splitters:
            splitter.splitterMoved.connect(self.schedule_save_state)
        log.info(f"✅ 已连接 {len(splitters)} 个QSplitter的信号")

    def toggle_preview(self):
        if self.preview_dlg and self.preview_dlg.isVisible():
            self.preview_dlg.close()
            return
        
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
            
        try:
            item_id_item = self.table.item(rows[0].row(), 8)
            if not item_id_item:
                return
            item_id = int(item_id_item.text())
            
            session = self.db.get_session()
            from data.database import ClipboardItem
            item = session.query(ClipboardItem).get(item_id)
            if item:
                if not self.preview_dlg:
                    self.preview_dlg = PreviewDialog(self)
                
                self.preview_dlg.load_data(item.content, item.item_type, item.file_path, item.image_path, item.data_blob)
                self.preview_dlg.show()
                self.preview_dlg.raise_()
                self.preview_dlg.activateWindow()
            session.close()
        except Exception as e:
            log.error(f"预览失败: {e}")

    def eventFilter(self, source, event):
        if source == self.table and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Space:
                self.toggle_preview()
                return True
        return super().eventFilter(source, event)

    def nativeEvent(self, eventType, message):
        if eventType == "windows_generic_MSG" and platform.system() == "Windows":
            msg = MSG.from_address(message.__int__())
            if msg.message == 0x0084:
                x = ctypes.c_short(msg.lParam & 0xFFFF).value
                y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                pos = self.mapFromGlobal(QPoint(x, y))
                w, h, m = self.width(), self.height(), self.border_width
                
                is_left = pos.x() < m
                is_right = pos.x() > w - m
                is_top = pos.y() < m
                is_bottom = pos.y() > h - m
                
                if is_top and is_left: return True, 13
                if is_top and is_right: return True, 14
                if is_bottom and is_left: return True, 16
                if is_bottom and is_right: return True, 17
                if is_left: return True, 10
                if is_right: return True, 11
                if is_top: return True, 12
                if is_bottom: return True, 15
                
                if self.title_bar:
                    title_pos = self.title_bar.mapFromGlobal(QPoint(x, y))
                    if self.title_bar.rect().contains(title_pos) and not self.title_bar.childAt(title_pos):
                        return True, 2
                        
        return super().nativeEvent(eventType, message)

    def show_context_menu(self, pos):
        self.menu_handler.show_menu(pos)

    def track_active_window(self):
        if platform.system() == "Windows":
            try:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                if hwnd and hwnd != int(self.winId()):
                    self.last_external_hwnd = hwnd
            except:
                pass

    def setup_shortcuts(self):
        for i in range(6):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self).activated.connect(lambda l=i: self.batch_set_star_shortcut(l))
        QShortcut(QKeySequence("Ctrl+G"), self).activated.connect(self.group_items_shortcut)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self.toggle_favorite_shortcut)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.toggle_lock_shortcut)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.focus_search_shortcut)
        QShortcut(QKeySequence("Del"), self).activated.connect(lambda: self.smart_delete(force_warn=False))
        QShortcut(QKeySequence("Ctrl+Shift+Del"), self).activated.connect(lambda: self.smart_delete(force_warn=True))

    def group_items_shortcut(self):
        self._batch_action("智能成组", lambda ids: self.menu_handler.batch_group_smart(ids))

    def toggle_favorite_shortcut(self):
        self._batch_action("切换收藏", lambda ids: self.menu_handler.batch_toggle(ids, 'is_favorite'))
        
    def toggle_lock_shortcut(self):
        self._batch_action("切换锁定", lambda ids: self.menu_handler.batch_toggle(ids, 'is_locked'))
        
    def focus_search_shortcut(self):
        if hasattr(self, 'title_bar') and hasattr(self.title_bar, 'search_bar'):
            self.title_bar.search_bar.setFocus()
            self.title_bar.search_bar.selectAll()

    def _batch_action(self, name, action_func):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        
        ids = []
        for r in rows:
            item = self.table.item(r.row(), 8)
            if item and item.text():
                ids.append(int(item.text()))
        
        if ids:
            log.info(f"⌨️ 快捷键触发: {name} ({len(ids)} 项)")
            action_func(ids)

    def smart_delete(self, force_warn=False):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        
        ids = [int(self.table.item(r.row(), 8).text()) for r in rows if self.table.item(r.row(), 8) and self.table.item(r.row(), 8).text()]
        if not ids:
            return
        
        is_in_trash = getattr(self.table, 'is_trash_view', False)
        
        session = self.db.get_session()
        from data.database import ClipboardItem
        items = session.query(ClipboardItem).filter(ClipboardItem.id.in_(ids)).all()
        deletable_ids = [item.id for item in items if not item.is_favorite and not item.is_locked]
        skipped_count = len(ids) - len(deletable_ids)
        session.close()
        
        if not deletable_ids:
            self.lbl_status.setText(f"⚠️ 选中的 {len(ids)} 个项目均受保护，操作取消")
            return

        if is_in_trash:
            msg = f"确定要【永久删除】这 {len(deletable_ids)} 个项目吗？\n该操作不可撤销！"
            if skipped_count > 0:
                msg += f"\n(已自动跳过 {skipped_count} 个受保护的项目)"
            
            if QMessageBox.warning(self, "永久删除确认", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
                self.db.delete_items_permanently(deletable_ids)
                self.lbl_status.setText(f"🔥 已永久删除 {len(deletable_ids)} 项")
            else:
                return
        else:
            if force_warn or len(deletable_ids) > 10:
                msg = f"确定要将这 {len(deletable_ids)} 个项目移动到回收站吗?"
                if skipped_count > 0:
                    msg += f"\n(已自动跳过 {skipped_count} 个受保护项目)"
                if QMessageBox.question(self, "确认删除", msg, QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                    return
            
            self.db.move_items_to_trash(deletable_ids)
            self.lbl_status.setText(f"✅ 已移动 {len(deletable_ids)} 项到回收站")

        self.load_data()
        self.partition_panel.refresh_partitions()

    def batch_set_star_shortcut(self, lvl):
        self._batch_action(f"设置星级为 {lvl}", lambda ids: self.menu_handler.batch_set_star(ids, lvl))

    def schedule_save_state(self):
        self.save_timer.start()

    def save_window_state(self):
        log.info("💾 保存窗口状态...")
        s = QSettings("ClipboardPro", "WindowState_v7")
        s.setValue("geometry", self.saveGeometry())
        s.setValue("windowState", self.dock_container.saveState())
        s.setValue("editMode", self.edit_mode)
        s.setValue("current_theme", self.current_theme)
        s.setValue("columnWidths", [self.table.columnWidth(i) for i in range(self.table.columnCount())])
        header = self.table.horizontalHeader()
        s.setValue("columnOrder", [header.visualIndex(i) for i in range(self.table.columnCount())])
        for i, align in self.col_alignments.items():
            s.setValue(f"col_{i}_align", align)
        s.setValue("is_pinned", self.is_pinned)
        s.setValue("pageSize", self.page_size)
        log.info("✅ 窗口状态已保存")

    def restore_window_state(self):
        log.info("💾 恢复窗口状态...")
        s = QSettings("ClipboardPro", "WindowState_v7")
        
        if g := s.value("geometry"):
            self.restoreGeometry(g)
        
        screen_geo = QApplication.desktop().availableGeometry()
        curr_geo = self.geometry()
        if curr_geo.height() > screen_geo.height() or curr_geo.top() < 0 or curr_geo.left() < 0:
             log.warning("⚠️ 检测到窗口尺寸异常，正在重置为安全尺寸...")
             init_w = min(1200, int(screen_geo.width() * 0.9))
             init_h = min(700, int(screen_h * 0.9))
             self.resize(init_w, init_h)
             self.move((screen_w - init_w) // 2, (screen_h - init_h) // 2)

        if ws := s.value("windowState"):
            self.dock_container.restoreState(ws)
        else:
            main_width = self.dock_container.width()
            left_width = int(main_width * 0.20)
            right_width = int(main_width * 0.25)
            left_docks = [d for d in [self.dock_filter, self.dock_partition, self.dock_tags] if d.isVisible()]
            right_docks = [d for d in [self.dock_detail] if d.isVisible()]
            if left_docks:
                self.dock_container.resizeDocks(left_docks, [left_width] * len(left_docks), Qt.Horizontal)
            if right_docks:
                self.dock_container.resizeDocks(right_docks, [right_width] * len(right_docks), Qt.Horizontal)

        self.is_pinned = s.value("is_pinned", False, type=bool)
        if self.is_pinned:
            self.toggle_pin(True)
        if hasattr(self.title_bar, 'btn_pin'):
            self.title_bar.btn_pin.setChecked(self.is_pinned)

        # Allow restoreState to handle visibility; do not force show all docks.
        for dock in [self.dock_filter, self.dock_partition, self.dock_tags, self.dock_detail]:
            dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        self.edit_mode = s.value("editMode", False, type=bool)
        if hasattr(self.title_bar, 'btn_mode'):
            self.title_bar.btn_mode.setChecked(self.edit_mode)
        self.toggle_edit_mode(self.edit_mode)

        self.page_size = s.value("pageSize", 100, type=int)
        if hasattr(self, 'title_bar'):
            self.title_bar.set_display_count(self.page_size)
        
        if cw := s.value("columnWidths"):
            for i, w in enumerate([int(w) for w in cw]): 
                if i < self.table.columnCount():
                    self.table.setColumnWidth(i, w)
        if co := s.value("columnOrder"):
            header = self.table.horizontalHeader()
            for logical_idx, visual_idx in enumerate(co):
                header.moveSection(header.visualIndex(logical_idx), int(visual_idx))
        
        for i in range(self.table.columnCount()):
            if align := s.value(f"col_{i}_align"):
                self.col_alignments[i] = int(align)
        
        self.apply_theme(s.value("current_theme", "dark"))
        log.info("✅ 窗口状态已恢复")

    def handle_dock_visibility_changed(self, visible):
        if not visible:
            log.info("智能布局触发：侧栏变动")
            left_docks = [d for d in [self.dock_filter, self.dock_partition, self.dock_tags] if d.isVisible() and not d.isFloating()]
            right_docks = [d for d in [self.dock_detail] if d.isVisible() and not d.isFloating()]
            QTimer.singleShot(10, lambda: self._do_smart_resize(left_docks, right_docks))

    def _do_smart_resize(self, left_docks, right_docks):
        try:
            if left_docks:
                self.dock_container.resizeDocks(left_docks, [d.width() for d in left_docks], Qt.Horizontal)
            if right_docks:
                self.dock_container.resizeDocks(right_docks, [d.width() for d in right_docks], Qt.Horizontal)
        except Exception as e:
            log.debug(f"智能布局调整略过: {e}")

    def closeEvent(self, e):
        self.save_window_state()
        e.accept()

    def on_clipboard_event(self):
        """
        剪贴板数据变化事件处理（防抖）。
        将事件数据加入队列并启动一个短定时器。
        """
        mime_data = self.clipboard.mimeData()
        self._clipboard_queue.append(mime_data)
        # 200ms 内的连续事件将被合并处理
        self._clipboard_timer.start(200)

    def _process_clipboard_queue(self):
        """
        定时器超时后处理剪贴板队列。
        只处理队列中最新的数据项。
        """
        if not self._clipboard_queue:
            return
        
        # 只处理最新的数据，并清空队列以忽略中间事件
        latest_mime_data = self._clipboard_queue[-1]
        self._clipboard_queue.clear()

        try:
            log.info("⏳ 处理防抖后的剪贴板事件...")
            self.cm.process_clipboard(latest_mime_data, self.partition_panel.get_current_selection())
        except Exception as e:
            log.error(f"处理剪贴板队列失败: {e}", exc_info=True)

    def refresh_after_capture(self):
        QTimer.singleShot(0, self.load_data)
        QTimer.singleShot(0, self.partition_panel.refresh_partitions)

    def go_to_first_page(self):
        self.page = 1
        self.load_data()

    def go_to_last_page(self):
        if self.page_size > 0:
            total_pages = (self.total_items + self.page_size - 1) // self.page_size
            self.page = total_pages if total_pages > 0 else 1
            self.load_data()

    def prev_page(self): 
        if self.page > 1:
            self.page -= 1
            self.load_data()

    def next_page(self):
        total_pages = (self.total_items + self.page_size - 1) // self.page_size if self.page_size > 0 else 1
        if self.page < total_pages:
            self.page += 1
            self.load_data()

    def load_data(self, reset_page=False):
        try:
            log.info(f"🔄 开始加载数据 (reset_page={reset_page})")
            if reset_page:
                self.page = 1
            
            partition_filter = self.partition_panel.get_current_selection()
            date_filter = self.filter_panel.get_checked('date_create')[0] if self.filter_panel.get_checked('date_create') else None
            date_modify_filter = self.filter_panel.get_checked('date_modify')[0] if self.filter_panel.get_checked('date_modify') else None
            
            if partition_filter and partition_filter.get('type') == 'today':
                date_modify_filter = '今日'
                partition_filter = None
            
            self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
            self.table.is_trash_view = bool(partition_filter and partition_filter.get('type') == 'trash')

            log.info(f"🔍 数据库筛选条件: 分区={partition_filter}, 创建日期={date_filter}, 修改日期={date_modify_filter}")
            
            self.total_items = self.db.get_count(partition_filter=partition_filter, date_filter=date_filter, date_modify_filter=date_modify_filter)
            
            limit, offset = self.page_size, 0
            if self.page_size != -1:
                self.bottom_bar.show()
                total_pages = (self.total_items + self.page_size - 1) // self.page_size if self.page_size > 0 else 1
                self.lbl_page.setText(f"{self.page} / {max(1, total_pages)}")
                
                is_first = self.page == 1
                is_last = self.page == total_pages or total_pages == 0
                
                self.btn_first.setEnabled(not is_first)
                self.btn_prev.setEnabled(not is_first)
                self.btn_next.setEnabled(not is_last)
                self.btn_last.setEnabled(not is_last)
                
                offset = (self.page - 1) * self.page_size
            else:
                self.bottom_bar.show()
                limit = None
                self.lbl_page.setText("1 / 1")
                self.btn_first.setEnabled(False)
                self.btn_prev.setEnabled(False)
                self.btn_next.setEnabled(False)
                self.btn_last.setEnabled(False)

            items = self.db.get_items_detached(sort_mode=self.current_sort_mode, limit=limit, offset=offset, date_filter=date_filter, date_modify_filter=date_modify_filter, partition_filter=partition_filter)

            # 清理旧缓存以防内存泄漏
            self.cached_items.clear()
            self.cached_items_map.clear()
            
            self.cached_items = items
            self.cached_items_map = {item.id: item for item in items}
            log.info(f"✅ 从数据库加载 {len(items)} 条数据并缓存")
            
            self.table.setUpdatesEnabled(False)
            self.table.blockSignals(True)

            try:
                self.table.setRowCount(len(items))
                for row, item in enumerate(items):
                    self.table.setItem(row, 8, QTableWidgetItem(str(item.id)))
                
                st_flags = ("📌" if item.is_pinned else "") + ("❤️" if item.is_favorite else "") + ("🔒" if item.is_locked else "")
                display_text = f"{self._get_type_icon(item)} {st_flags}".strip()
                state_item = QTableWidgetItem(display_text)
                if item.custom_color:
                    state_item.setIcon(get_color_icon(item.custom_color))
                self.table.setItem(row, 0, state_item)
                
                self.table.setItem(row, 1, QTableWidgetItem(item.content.replace('\n', ' ')[:100]))
                self.table.setItem(row, 2, QTableWidgetItem(item.note))
                self.table.setItem(row, 3, QTableWidgetItem("★" * item.star_level))
                self.table.setItem(row, 4, QTableWidgetItem(format_size(item.content)))
                
                if item.is_file and item.file_path:
                    _, ext = os.path.splitext(item.file_path)
                    type_str = ext.upper()[1:] if ext else "FILE"
                else:
                    type_str = "TXT"
                self.table.setItem(row, 5, QTableWidgetItem(type_str))
                
                self.table.setItem(row, 6, QTableWidgetItem(item.created_at.strftime("%m-%d %H:%M")))
                self.table.setItem(row, 7, QTableWidgetItem(item.file_path or ""))
                
                for col in range(7):
                    align = self.col_alignments.get(col, Qt.AlignLeft | Qt.AlignVCenter if col in [1,2] else Qt.AlignCenter)
                    table_item = self.table.item(row, col)
                    if table_item:
                        table_item.setTextAlignment(align)
            finally:
                self.table.blockSignals(False)
                self.table.setUpdatesEnabled(True)
            
            self._apply_frontend_filters()
            self.tag_panel.refresh_tags(self.db)
            
            if self.item_id_to_select_after_load is not None:
                self.select_item_in_table(self.item_id_to_select_after_load)
                self.item_id_to_select_after_load = None
            
            log.info("✅ 数据加载完成")
        except Exception as e:
            log.error(f"Load Error: {e}", exc_info=True)

    def _apply_frontend_filters(self):
        log.info("🎭 应用前端过滤...")
        search_text = self.title_bar.get_search_text().strip().lower()
        stars = set(self.filter_panel.get_checked('stars'))
        colors = set(self.filter_panel.get_checked('colors'))
        types = set(self.filter_panel.get_checked('types'))
        tags = set(self.filter_panel.get_checked('tags'))
        
        log.debug(f"   筛选条件: 搜索='{search_text}', 星级={stars}, 颜色={colors}, 类型={types}, 标签={tags}")
        
        visible_count = 0
        for row in range(self.table.rowCount()):
            should_show = True
            id_item = self.table.item(row, 8)
            if not id_item or not id_item.text():
                self.table.setRowHidden(row, True)
                continue
            
            item = self.cached_items_map.get(int(id_item.text()))
            if not item:
                self.table.setRowHidden(row, True)
                continue
            
            if search_text and not (search_text in item.content.lower() or search_text in (item.note or "").lower() or any(search_text in tag.name.lower() for tag in item.tags)):
                should_show = False
            if should_show and stars and item.star_level not in stars:
                should_show = False
            if should_show and colors and (not item.custom_color or item.custom_color not in colors):
                should_show = False
            if should_show and types and self._get_item_type_key(item) not in types:
                should_show = False
            if should_show and tags and not {tag.name for tag in item.tags}.intersection(tags):
                should_show = False
            
            self.table.setRowHidden(row, not should_show)
            if should_show:
                visible_count += 1
        
        log.info(f"✅ 前端过滤完成: 显示 {visible_count}/{len(self.cached_items)} 行")
        
        # Correct Logic: Stats should be calculated from all items on the page
        # to prevent filter options from disappearing when a filter is applied.
        stats = self._calculate_stats_from_items(self.cached_items)
        self.filter_panel.update_stats(stats)
        
        self.lbl_status.setText(f"总计: {self.total_items} 条 | 当前页: {len(self.cached_items)} 条 | 显示: {visible_count} 条")

    def _get_type_icon(self, item):
        if item.item_type == 'url': return "🔗"
        if item.item_type == 'image': return "🖼️"
        if item.item_type == 'file' and item.file_path:
            if os.path.exists(item.file_path):
                if os.path.isdir(item.file_path): return "📂"
                ext = os.path.splitext(item.file_path)[1].lower()
                if ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma']: return "🎵"
                if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp']: return "🖼️"
                if ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv']: return "🎬"
                return "📄"
            return "📄"
        return "📝"

    def _get_item_type_key(self, item):
        if item.item_type == 'text': return 'text'
        if item.item_type == 'url': return 'url'
        if item.item_type == 'file' and item.file_path:
            if os.path.exists(item.file_path):
                if os.path.isdir(item.file_path): return 'folder'
                _, ext = os.path.splitext(item.file_path)
                return ext.lstrip('.').upper() if ext else 'FILE'
            return 'FILE'
        if item.item_type == 'image':
            path = item.image_path or item.file_path
            if path:
                _, ext = os.path.splitext(path)
                return ext.lstrip('.').upper() if ext else 'IMAGE'
            return 'IMAGE'
        return 'text'

    def _calculate_stats_from_items(self, items):
        """基于给定的 item 列表计算前端筛选器所需的统计信息"""
        if not items:
            return {'tags': [], 'stars': {}, 'colors': {}, 'types': {}, 'date_create': {}, 'date_modify': {}}

        item_ids = [item.id for item in items]
        
        # 从数据库高效获取核心统计数据
        stats = self.db.get_stats_for_items(item_ids)
        
        # 在客户端计算剩余的、逻辑较复杂的统计数据
        stats['types'] = {}
        stats['date_create'] = {}
        stats['date_modify'] = {}

        for item in items:
            # 类型统计
            stats['types'][self._get_item_type_key(item)] = stats['types'].get(self._get_item_type_key(item), 0) + 1

            # 日期统计
            label = get_date_label(item.created_at)
            if label:
                stats['date_create'][label] = stats['date_create'].get(label, 0) + 1
            if item.modified_at:
                label = get_date_label(item.modified_at)
                if label:
                    stats['date_modify'][label] = stats['date_modify'].get(label, 0) + 1

        # 确保标签格式正确
        stats['tags'] = list(stats['tags'].items())

        return stats

    def show_header_menu(self, pos):
        col = self.table.horizontalHeader().logicalIndexAt(pos)
        menu = QMenu()
        menu.addAction("← 左对齐").triggered.connect(lambda: self.set_col_align(col, Qt.AlignLeft | Qt.AlignVCenter))
        menu.addAction("↔ 居中").triggered.connect(lambda: self.set_col_align(col, Qt.AlignCenter))
        menu.addAction("→ 右对齐").triggered.connect(lambda: self.set_col_align(col, Qt.AlignRight | Qt.AlignVCenter))
        menu.exec_(self.table.horizontalHeader().mapToGlobal(pos))
        
    def set_col_align(self, col, align):
        self.col_alignments[col] = int(align)
        for row in range(self.table.rowCount()):
            table_item = self.table.item(row, col)
            if table_item:
                table_item.setTextAlignment(align)
        self.schedule_save_state()

    def on_display_count_changed(self, count):
        self.page_size = count
        self.load_data(reset_page=True)

    def toggle_pin(self, checked):
        if platform.system() == "Windows":
            try:
                log.info(f"📌 切换窗口置顶状态: {checked}")
                self.is_pinned = checked
                hwnd = int(self.winId())
                flag = HWND_TOPMOST if checked else HWND_NOTOPMOST
                SetWindowPos(hwnd, flag, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
                self.schedule_save_state()
            except Exception as e:
                log.error(f"❌ 置顶设置失败: {e}", exc_info=True)

    def auto_clean(self):
        if QMessageBox.question(self, "确认", "删除21天前未锁定的旧数据?") == QMessageBox.Yes:
             count = self.db.auto_delete_old_data(days=21)
             QMessageBox.information(self, "完成", f"清理了 {count} 条旧数据")
             self.load_data()

    def toggle_edit_mode(self, checked):
        self.edit_mode = checked
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked if checked else QAbstractItemView.NoEditTriggers)
        self.schedule_save_state()

    def on_table_double_click(self, item):
        if self.edit_mode:
            return
        self.copy_and_paste_item()

    def on_item_changed(self, item):
        if not self.edit_mode:
            return
        
        row, col = item.row(), item.column()
        item_id = int(self.table.item(row, 8).text())
        if col == 1:
            self.db.update_item(item_id, content=item.text().strip())
        elif col == 2:
            self.db.update_item(item_id, note=item.text().strip())
        
        self.load_data()

    def copy_and_paste_item(self):
        if self.current_item_id:
            session = self.db.get_session()
            from data.database import ClipboardItem
            obj = session.query(ClipboardItem).get(self.current_item_id)
            if obj:
                self._processing_clipboard = True
                try:
                    if obj.item_type == 'image' and obj.data_blob:
                        image = QImage()
                        image.loadFromData(obj.data_blob)
                        self.clipboard.setImage(image)
                    else:
                        self.clipboard.setText(obj.content)
                finally:
                    self._processing_clipboard = False
                
                if self.last_external_hwnd and platform.system() == "Windows":
                    self.showMinimized()
                    try:
                        ctypes.windll.user32.SetForegroundWindow(self.last_external_hwnd)
                        if ctypes.windll.user32.IsIconic(self.last_external_hwnd):
                            ctypes.windll.user32.ShowWindow(self.last_external_hwnd, 9)
                    except:
                        pass
                    QTimer.singleShot(100, self._send_ctrl_v)
                else:
                    self.lbl_status.setText("✅ 已复制")
            session.close()

    def _send_ctrl_v(self):
        if platform.system() == "Windows":
            ctypes.windll.user32.keybd_event(0x11, 0, 0, 0) # CTRL
            ctypes.windll.user32.keybd_event(0x56, 0, 0, 0) # V
            ctypes.windll.user32.keybd_event(0x56, 2, 0) # V up
            ctypes.windll.user32.keybd_event(0x11, 2, 0) # CTRL up

    def update_detail_panel(self):
        rows = self.table.selectionModel().selectedRows()
        has_selection = bool(rows)
        self.tag_panel.setEnabled(has_selection)

        if not rows:
            self.detail_panel.clear()
            return
        
        item = self.table.item(rows[0].row(), 8)
        if not item or not item.text():
            log.warning("⚠️ 选中行的ID列为空")
            return
        
        item_id = int(item.text())
        log.debug(f"📋 更新详情面板，项目ID: {item_id}")
        session = self.db.get_session()
        from data.database import ClipboardItem
        item_obj = session.query(ClipboardItem).options(joinedload(ClipboardItem.tags), joinedload(ClipboardItem.partition)).get(item_id)
        
        if item_obj:
            tags = [t.name for t in item_obj.tags]
            path_parts = []
            curr = item_obj.partition
            while curr:
                path_parts.append(curr.name)
                curr = session.query(Partition).get(curr.parent_id)
            path_parts.reverse()
            group_name = path_parts[0] if path_parts else None
            partition_name = " -> ".join(path_parts) if path_parts else None

            self.detail_panel.load_item(item_obj.content, item_obj.note, tags, group_name=group_name, partition_name=partition_name, item_type=item_obj.item_type, image_path=item_obj.image_path, file_path=item_obj.file_path, image_blob=item_obj.data_blob)
            self.current_item_id = item_id
        session.close()

    def reorder_items(self, new_ids):
        self.db.update_sort_order(new_ids)

    def save_note(self, text):
        if self.current_item_id:
            self.db.update_item(self.current_item_id, note=text)
            self.load_data()
    
    def on_tags_added(self, tags):
        if self.current_item_id:
            self.db.add_tags_to_items([self.current_item_id], tags)
            self.update_detail_panel()
            self.load_data()
            self.partition_panel.refresh_partitions()

    def on_tag_panel_commit_tags(self, tags):
        rows = self.table.selectionModel().selectedRows()
        if not rows or not tags:
            return
        
        item_ids = [int(self.table.item(r.row(), 8).text()) for r in rows if self.table.item(r.row(), 8) and self.table.item(r.row(), 8).text()]
        if item_ids:
            self.db.add_tags_to_items(item_ids, tags)
            self.load_data()
            self.update_detail_panel()
            self.partition_panel.refresh_partitions()
            log.info(f"✅ 已为 {len(item_ids)} 个项目批量添加标签: {tags}")

    def remove_tag(self, tag):
        if self.current_item_id: 
            self.db.remove_tag_from_item(self.current_item_id, tag)
            self.update_detail_panel()
            self.load_data()
            self.partition_panel.refresh_partitions()

    def toggle_theme(self):
        self.apply_theme("light" if self.current_theme == "dark" else "dark")

    def apply_theme(self, name):
        self.current_theme = name
        app = QApplication.instance()
        if name == "dark":
            app.setStyleSheet(themes.dark.STYLESHEET)
        else:
            app.setStyleSheet(themes.light.STYLESHEET)
    
    def toolbar_set_color(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        
        item_ids = [int(self.table.item(r.row(), 8).text()) for r in rows if self.table.item(r.row(), 8) and self.table.item(r.row(), 8).text()]
        if item_ids:
            self.set_custom_color(item_ids)

    def set_custom_color(self, item_ids):
        dlg = ColorSelectorDialog(self)
        if dlg.exec_():
            self.batch_set_color(item_ids, dlg.selected_color or "")

    def batch_set_color(self, ids, clr):
        session = self.db.get_session()
        try:
            from data.database import ClipboardItem
            count = session.query(ClipboardItem).filter(ClipboardItem.id.in_(ids)).update({'custom_color': clr}, synchronize_session=False)
            session.commit()
            log.info(f"✅ 成功设置 {count} 个项目的颜色")
            self.load_data()
        except Exception as e:
            log.error(f"❌ 设置颜色失败: {e}", exc_info=True)
            session.rollback()
        finally:
            session.close()
        self.schedule_save_state()

    def select_item_in_table(self, item_id_to_select):
        log.debug(f"滚动到项目: {item_id_to_select}")
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 8)
            if item and item.text() == str(item_id_to_select):
                self.table.blockSignals(True)
                self.table.selectRow(row)
                self.table.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                self.table.blockSignals(False)
                log.info(f"✅ 已在表格中高亮显示项目 {item_id_to_select}")
                return
        log.warning(f"⚠️ 未能在当前显示的表格中找到项目ID: {item_id_to_select}")
    
    def on_tag_panel_add_tag(self, tag_input=None):
        if not tag_input:
            dlg = TagDialog(self.db, self)
            if dlg.exec_():
                self.tag_panel.refresh_tags(self.db)
            return

        tags_to_add = tag_input if isinstance(tag_input, list) else [tag_input]
        session = self.db.get_session()
        from data.database import Tag
        try:
            has_new = False
            for tag_name in [t.strip() for t in tags_to_add if t.strip()]:
                if not session.query(Tag).filter_by(name=tag_name).first():
                    session.add(Tag(name=tag_name))
                    has_new = True
            if has_new:
                session.commit()
                self.tag_panel.refresh_tags(self.db)
        except Exception as e:
            log.error(f"添加标签失败: {e}")
        finally:
            session.close()
    
    def on_tag_selected(self, tag_name):
        log.info(f"🏷️ 标签被选中: {tag_name}")

    def handle_item_selection_in_partition(self, item_id):
        log.debug(f"接收到侧边栏高亮请求，项目ID: {item_id}，将在加载后处理。")
        self.item_id_to_select_after_load = item_id
