# -*- coding: utf-8 -*-
import logging
import ctypes
import os
from ctypes.wintypes import MSG

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
from ui.dialog_preview import PreviewDialog # 新增预览对话框

import themes.dark
import themes.light

# 配置日志
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("MainWindow")

# Windows API
SetWindowPos = ctypes.windll.user32.SetWindowPos
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
        
        # 1. 智能初始化尺寸 (解决窗口过高问题)
        screen_geo = QApplication.desktop().availableGeometry()
        screen_w, screen_h = screen_geo.width(), screen_geo.height()
        
        # 默认宽1200，高700，但不能超过屏幕的 90%
        init_w = min(1200, int(screen_w * 0.9))
        init_h = min(700, int(screen_h * 0.9))
        self.resize(init_w, init_h)
        
        # 将窗口居中
        self.move((screen_w - init_w) // 2, (screen_h - init_h) // 2)
        
        # 2. 无边框设置
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True) # 开启鼠标追踪，辅助光标判定
        
        # 3. 边缘判定范围 (加大到 8px 确保能轻松点到)
        self.border_width = 8
        
        # 变量
        self.edit_mode = False
        self.current_sort_mode = "manual" # 保留排序模式，但不提供UI切换
        self.last_external_hwnd = None
        self.col_alignments = {} 
        self.current_item_id = None
        self.page = 1
        self.page_size = 100 # 默认每页100条
        self.total_items = 0
        self._processing_clipboard = False  # 防止剪贴板事件重复处理
        self.item_id_to_select_after_load = None # 用于处理列表加载后的高亮
        
        # 定时器
        self.save_timer = QTimer(); self.save_timer.setSingleShot(True); self.save_timer.setInterval(500)
        self.save_timer.timeout.connect(self.save_window_state)
        
        self.focus_timer = QTimer(); self.focus_timer.timeout.connect(self.track_active_window)
        self.focus_timer.start(200)
        
        # 服务
        self.db = DBManager()
        self.cm = ClipboardManager(self.db)
        self.cm.data_captured.connect(self.refresh_after_capture) 
        
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_event)
        
        # 界面
        self.setup_ui()
        self.menu_handler = ContextMenuHandler(self)
        self.setup_shortcuts()
        
        # 恢复状态 (使用新Key强制重置布局)
        self.restore_window_state()
        self.load_data()
        
        log.info("✅ 主窗口启动完毕")

    def setup_ui(self):
        # 1. 物理边缘
        # 这里设置为 0 或很小，配合 nativeEvent 的 border_width 使用
        # 稍微留一点 margin 可以让阴影或边框显示出来，但如果太大容易导致鼠标穿透
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.outer_layout = QVBoxLayout(self.central_widget)
        # 设置与 border_width 一致或略小的 margin
        self.outer_layout.setContentsMargins(5, 5, 5, 5) 
        self.outer_layout.setSpacing(0)
        
        # 2. 视觉容器 - 添加圆角
        self.big_container = QFrame()
        self.big_container.setObjectName("MainFrame")
        self.outer_layout.addWidget(self.big_container)
        self.inner_layout = QVBoxLayout(self.big_container)
        self.inner_layout.setContentsMargins(0, 0, 0, 0)
        self.inner_layout.setSpacing(0)
        
        # 3. 标题栏
        self.title_bar = CustomTitleBar(self)
        self.title_bar.refresh_clicked.connect(self.load_data)
        self.title_bar.theme_clicked.connect(self.toggle_theme)
        self.title_bar.search_changed.connect(lambda: self.load_data(reset_page=True))
        # self.title_bar.sort_changed.connect(self.change_sort) # 移除旧的连接
        self.title_bar.display_count_changed.connect(self.on_display_count_changed) # 添加新的连接
        self.title_bar.pin_clicked.connect(self.toggle_pin)
        self.title_bar.clean_clicked.connect(self.auto_clean)
        self.title_bar.mode_clicked.connect(self.toggle_edit_mode)
        self.title_bar.color_clicked.connect(self.toolbar_set_color)  # 连接颜色按钮
        self.inner_layout.addWidget(self.title_bar)
        
        # 4. Dock 容器
        self.dock_container = QMainWindow()
        self.dock_container.setWindowFlags(Qt.Widget)
        
        # 关键：移除AllowTabbedDocks，禁止标签页模式，强制分割模式
        self.dock_container.setDockOptions(
            QMainWindow.AllowNestedDocks |      # 允许嵌套
            QMainWindow.AnimatedDocks |         # 动画效果
            QMainWindow.GroupedDragging         # 分组拖动
            # 不使用 AllowTabbedDocks！
        )
        
        # 关键：设置角落策略，强制水平优先
        # 左侧区域的上下角都归左侧，右侧区域的上下角都归右侧
        # 这样可以最大化水平空间
        self.dock_container.setCorner(Qt.TopLeftCorner, Qt.LeftDockWidgetArea)
        self.dock_container.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        self.dock_container.setCorner(Qt.TopRightCorner, Qt.RightDockWidgetArea)
        self.dock_container.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)
        
        self.inner_layout.addWidget(self.dock_container, 1) 
        
        # --- 左侧面板组 ---
        # 筛选器面板
        self.dock_filter = QDockWidget("筛选器", self.dock_container)
        self.dock_filter.setObjectName("DockFilter")
        self.dock_filter.setTitleBarWidget(CustomDockTitleBar("筛选器", self.dock_filter, self.dock_container))
        self.dock_filter.setFeatures(QDockWidget.AllDockWidgetFeatures) # 启用所有特征，包括悬浮可调整大小
        self.dock_filter.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        self.filter_panel = FilterPanel() 
        self.filter_panel.filterChanged.connect(lambda: self.load_data(reset_page=True))
        self.dock_filter.setWidget(self.filter_panel)
        self.dock_container.addDockWidget(Qt.LeftDockWidgetArea, self.dock_filter)
        
        # 分区组面板
        self.dock_partition = QDockWidget("分区组", self.dock_container)
        self.dock_partition.setObjectName("DockPartition")
        self.dock_partition.setTitleBarWidget(CustomDockTitleBar("分区组", self.dock_partition, self.dock_container))
        self.dock_partition.setFeatures(QDockWidget.AllDockWidgetFeatures)
        self.dock_partition.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.partition_panel = PartitionPanel(self.db)
        self.partition_panel.partitionSelectionChanged.connect(lambda: self.load_data(reset_page=True))
        
        # 核心修复: 当分区数据结构更新时 (例如添加/删除), 才刷新整个分区面板和主列表
        self.partition_panel.partitionsUpdated.connect(self.partition_panel.refresh_partitions)
        self.partition_panel.partitionsUpdated.connect(self.load_data)

        self.dock_partition.setWidget(self.partition_panel)
        self.dock_container.addDockWidget(Qt.LeftDockWidgetArea, self.dock_partition)

        # 标签面板（新增）
        self.dock_tags = QDockWidget("标签", self.dock_container)
        self.dock_tags.setObjectName("DockTags")
        self.dock_tags.setTitleBarWidget(CustomDockTitleBar("标签", self.dock_tags, self.dock_container))
        self.dock_tags.setFeatures(QDockWidget.AllDockWidgetFeatures)
        self.dock_tags.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        self.tag_panel = TagPanel()
        self.tag_panel.setEnabled(False)  # 默认禁用
        self.tag_panel.tags_committed.connect(self.on_tag_panel_commit_tags) # 连接到新的批量添加槽
        # self.tag_panel.add_tag_requested.connect(self.on_tag_panel_add_tag) # 断开旧的连接
        self.tag_panel.tag_selected.connect(self.on_tag_selected)
        self.dock_tags.setWidget(self.tag_panel)
        self.dock_container.addDockWidget(Qt.LeftDockWidgetArea, self.dock_tags)
        
        self.dock_container.splitDockWidget(self.dock_filter, self.dock_partition, Qt.Horizontal)
        self.dock_container.splitDockWidget(self.dock_partition, self.dock_tags, Qt.Horizontal)

        # --- 右 Dock ---
        self.dock_detail = QDockWidget("详细信息", self.dock_container)
        self.dock_detail.setObjectName("DockDetail")
        self.dock_detail.setTitleBarWidget(CustomDockTitleBar("详细信息", self.dock_detail, self.dock_container))
        self.dock_detail.setFeatures(QDockWidget.AllDockWidgetFeatures)
        self.dock_detail.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        self.detail_panel = DetailPanel() 
        self.detail_panel.update_note_signal.connect(self.save_note)
        self.detail_panel.tags_added_signal.connect(self.on_tags_added) # 连接新信号
        self.detail_panel.remove_tag_signal.connect(self.remove_tag)
        self.dock_detail.setWidget(self.detail_panel)
        self.dock_container.addDockWidget(Qt.RightDockWidgetArea, self.dock_detail)
        
        # --- 数据列表 (还原至中央区域) ---
        self.table = TablePanel()
        # 设置表格的大小策略
        from PyQt5.QtWidgets import QSizePolicy
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setMinimumWidth(300)  # 最小宽度，确保表格可用
        
        self.table.horizontalHeader().customContextMenuRequested.connect(self.show_header_menu)
        self.table.horizontalHeader().sectionResized.connect(self.schedule_save_state)
        self.table.itemSelectionChanged.connect(self.update_detail_panel)
        self.table.itemDoubleClicked.connect(self.on_table_double_click)
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.reorder_signal.connect(self.reorder_items)
        
        self.dock_container.setCentralWidget(self.table)
        
        # 关键：设置Dock面板的大小策略，使其可以灵活调整
        # 使用Preferred策略，允许面板在拖动时自动调整大小
        from PyQt5.QtWidgets import QSizePolicy
        
        # 为每个Dock面板的widget设置大小策略
        self.filter_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.partition_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.tag_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.detail_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        
        # 设置Dock面板的大小约束 - 恢复最小宽度至 230px
        log.info("📏 恢复面板最小宽度限制至 230px...")
        self.dock_container.setMouseTracking(True)
        
        # 统一将最小宽度恢复为 230
        min_w = 230
        self.dock_filter.setMinimumWidth(min_w)
        self.dock_partition.setMinimumWidth(min_w)
        self.dock_tags.setMinimumWidth(min_w)
        self.dock_detail.setMinimumWidth(min_w)
        
        # 显式移除最大宽度限制
        self.dock_filter.setMaximumWidth(16777215)
        self.dock_partition.setMaximumWidth(16777215)
        self.dock_tags.setMaximumWidth(16777215)
        self.dock_detail.setMaximumWidth(16777215)
        
        # 移除固定的初始宽度设置，改由 restore_window_state 按比例控制
        
        # 5. 底部栏
        self.bottom_bar = QWidget()
        self.bottom_bar.setFixedHeight(32)
        
        bl = QHBoxLayout(self.bottom_bar)
        bl.setContentsMargins(10, 0, 10, 0)
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setObjectName("StatusLabel")
        bl.addWidget(self.lbl_status); bl.addStretch()

        self.btn_first = QPushButton("« 首页"); self.btn_first.setFixedSize(80, 28)
        self.btn_prev = QPushButton("< 上一页"); self.btn_prev.setFixedSize(80, 28)
        self.lbl_page = QLabel("1 / 1")
        self.lbl_page.setObjectName("PageLabel")
        self.btn_next = QPushButton("下一页 >"); self.btn_next.setFixedSize(80, 28)
        self.btn_last = QPushButton("末页 »"); self.btn_last.setFixedSize(80, 28)

        self.btn_first.clicked.connect(self.go_to_first_page)
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
        
        # 连接自动保存与智能布局信号
        log.info("🔗 连接自动保存与智能布局信号...")
        for dock in [self.dock_filter, self.dock_partition, self.dock_tags, self.dock_detail]:
            # 当Dock的停靠位置改变时，触发状态保存
            dock.dockLocationChanged.connect(lambda: self.schedule_save_state())
            # 当Dock可见性改变时（拖出或关闭），执行智能布局调整
            dock.visibilityChanged.connect(self.handle_dock_visibility_changed)
        
        # 当表格列宽或顺序改变时，触发状态保存
        # 当表格列宽或顺序改变时，触发状态保存
        self.table.horizontalHeader().sectionResized.connect(lambda: self.schedule_save_state())
        self.table.horizontalHeader().sectionMoved.connect(lambda: self.schedule_save_state())

        # 核心修复：延迟连接所有内部分割器的移动信号
        # 这是用户手动调整宽度的唯一安全时机，也是保存状态的最佳时机。
        QTimer.singleShot(100, self.connect_splitters)

    def connect_splitters(self):
        """查找并连接所有QSplitter的信号到状态保存槽。"""
        log.debug("连接Dock容器中的QSplitter信号...")
        from PyQt5.QtWidgets import QSplitter
        splitters = self.dock_container.findChildren(QSplitter)
        for splitter in splitters:
            # 当用户拖动分隔条时，安排一次状态保存
            splitter.splitterMoved.connect(lambda: self.schedule_save_state())
        log.info(f"✅ 已连接 {len(splitters)} 个QSplitter的信号以在拖动后保存状态")

    # === 原生拖拽逻辑 (加强版) ===
        # 预览对话框实例 (懒加载)
        self.preview_dlg = None
        
        # 5. 事件过滤器 (用于捕获空格键)
        self.table.installEventFilter(self)
        
        log.info("✅ UI初始化完成")

    def toggle_preview(self):
        """切换快速预览"""
        # 如果已打开，则关闭
        if self.preview_dlg and self.preview_dlg.isVisible():
            self.preview_dlg.close()
            return
            
        # 获取选中的行
        rows = self.table.selectionModel().selectedRows()
        if not rows: return
        
        # 获取数据 (ID在第9列，索引8)
        try:
            item_id_item = self.table.item(rows[0].row(), 8)
            if not item_id_item: return
            item_id = int(item_id_item.text())
            
            # 查询数据库
            session = self.db.get_session()
            from data.database import ClipboardItem
            item = session.query(ClipboardItem).get(item_id)
            if item:
                # 初始化对话框 (如果不存在)
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
        # 监听表格的空格键
        if source == self.table and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Space:
                self.toggle_preview()
                return True # 消费事件，防止选中切换
        return super().eventFilter(source, event)

    def nativeEvent(self, eventType, message):
        """处理 Windows 原生消息，实现无边框窗口的拖动缩放"""
        if eventType == "windows_generic_MSG":
            msg = MSG.from_address(message.__int__())
            if msg.message == 0x0084: # WM_NCHITTEST
                # 获取鼠标位置 (处理负坐标和多屏)
                x = ctypes.c_short(msg.lParam & 0xFFFF).value
                y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                # 将全局坐标映射到窗口坐标系
                pos = self.mapFromGlobal(QPoint(x, y))
                
                w = self.width()
                h = self.height()
                m = self.border_width  # 使用增加后的边缘判定宽度
                
                # 判定鼠标是否在边缘区域
                is_left = pos.x() < m
                is_right = pos.x() > w - m
                is_top = pos.y() < m
                is_bottom = pos.y() > h - m
                
                # 优先级：角落 > 边缘 > 标题栏 > 客户区
                # 返回 Windows 定义的 HT 代码
                if is_top and is_left: return True, 13  # HTTOPLEFT
                if is_top and is_right: return True, 14  # HTTOPRIGHT
                if is_bottom and is_left: return True, 16  # HTBOTTOMLEFT
                if is_bottom and is_right: return True, 17  # HTBOTTOMRIGHT
                if is_left: return True, 10  # HTLEFT
                if is_right: return True, 11  # HTRIGHT
                if is_top: return True, 12  # HTTOP
                if is_bottom: return True, 15  # HTBOTTOM
                
                # 标题栏拖动区域判定
                # 将鼠标位置转换到标题栏坐标系
                if self.title_bar:
                    title_pos = self.title_bar.mapFromGlobal(QPoint(x, y))
                    if self.title_bar.rect().contains(title_pos):
                        # 如果鼠标在按钮上，则不作为标题栏处理（让按钮接收事件）
                        if not self.title_bar.childAt(title_pos):
                            return True, 2  # HTCAPTION
                        
        return super().nativeEvent(eventType, message)

    def show_context_menu(self, pos):
        # 代理给 Handler
        self.menu_handler.show_menu(pos)
    
    # ... (函数 force_horizontal_layout 和 untabify_all_docks 已被移除) ...

    def track_active_window(self):
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd and hwnd != int(self.winId()): self.last_external_hwnd = hwnd
        except: pass

    def setup_shortcuts(self):
        for i in range(6):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self).activated.connect(lambda l=i: self.batch_set_star_shortcut(l))
        # 快捷键增强
        QShortcut(QKeySequence("Ctrl+G"), self).activated.connect(self.group_items_shortcut)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self.toggle_favorite_shortcut)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.toggle_lock_shortcut)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.focus_search_shortcut)
        
        # 删除快捷键
        QShortcut(QKeySequence("Del"), self).activated.connect(lambda: self.smart_delete(force_warn=False))
        QShortcut(QKeySequence("Ctrl+Shift+Del"), self).activated.connect(lambda: self.smart_delete(force_warn=True))

    def group_items_shortcut(self):
        """Ctrl+G: 智能成组（随机色/取消）"""
        self._batch_action("智能成组", lambda ids: self.menu_handler.batch_group_smart(ids))

    def toggle_favorite_shortcut(self):
        """Ctrl+E: 切换收藏"""
        self._batch_action("切换收藏", lambda ids: self.menu_handler.batch_toggle(ids, 'is_favorite'))
        
    def toggle_lock_shortcut(self):
        """Ctrl+S: 切换锁定"""
        self._batch_action("切换锁定", lambda ids: self.menu_handler.batch_toggle(ids, 'is_locked'))
        
    def focus_search_shortcut(self):
        """Ctrl+F: 定位搜索框"""
        if hasattr(self, 'title_bar') and hasattr(self.title_bar, 'search_bar'):
            self.title_bar.search_bar.setFocus()
            self.title_bar.search_bar.selectAll()

    def _batch_action(self, name, action_func):
        """通用批量操作辅助函数"""
        rows = self.table.selectionModel().selectedRows()
        if not rows: return
        ids = []
        for r in rows:
            item = self.table.item(r.row(), 8)
            if item and item.text(): ids.append(int(item.text()))
        if ids:
            log.info(f"⌨️ 快捷键触发: {name} ({len(ids)} 项)")
            action_func(ids)

    def smart_delete(self, force_warn=False):
        """
        智能删除逻辑
        - 在常规视图：将项目移动到回收站
        - 在回收站视图：将项目永久删除
        """
        rows = self.table.selectionModel().selectedRows()
        if not rows: return
        
        # 1. 收集ID
        ids = []
        for r in rows:
            item = self.table.item(r.row(), 8)
            if item and item.text(): ids.append(int(item.text()))
        if not ids: return
        
        # 2. 检查视图状态
        is_in_trash = getattr(self.table, 'is_trash_view', False)
        
        # 3. 检查属性 (查询数据库)
        session = self.db.get_session()
        from data.database import ClipboardItem
        items = session.query(ClipboardItem).filter(ClipboardItem.id.in_(ids)).all()
        
        deletable_ids = []
        skipped_count = 0
        
        for item in items:
            # 只有非收藏且非锁定的项目可以被移动/删除
            if item.is_favorite or item.is_locked:
                skipped_count += 1
            else:
                deletable_ids.append(item.id)
        session.close()
        
        if not deletable_ids:
            self.statusBar().showMessage(f"⚠️ 选中的 {len(ids)} 个项目均被锁定或收藏，操作已取消", 3000)
            return

        # 4. 执行删除逻辑
        if is_in_trash:
            # 回收站内：永久删除 (强制确认)
            msg = f"确定要【永久删除】这 {len(deletable_ids)} 个项目吗？\n该操作不可撤销！"
            if skipped_count > 0:
                msg += f"\n(已自动跳过 {skipped_count} 个受保护的项目)"
                
            if QMessageBox.warning(self, "永久删除确认", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
                self.db.delete_items_permanently(deletable_ids)
                self.statusBar().showMessage(f"🔥 已永久删除 {len(deletable_ids)} 项", 3000)
            else:
                return
        else:
            # 常规视图：移至回收站
            if force_warn or len(deletable_ids) > 10: # 大批量删除时也提示一下
                msg = f"确定要将这 {len(deletable_ids)} 个项目移动到回收站吗?"
                if skipped_count > 0:
                    msg += f"\n(已自动跳过 {skipped_count} 个受保护项目)"
                if QMessageBox.question(self, "确认删除", msg, QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                    return
            
            self.db.move_items_to_trash(deletable_ids)
            self.statusBar().showMessage(f"✅ 已移动 {len(deletable_ids)} 项到回收站", 3000)

        # 5. 刷新界面
        self.load_data()
        self.partition_panel.refresh_partitions()

    def batch_set_star_shortcut(self, lvl):
        rows = self.table.selectionModel().selectedRows()
        if not rows: return
        ids = []
        for r in rows:
            item = self.table.item(r.row(), 8)
            if item and item.text():
                ids.append(int(item.text()))
        if ids:
            self.menu_handler.batch_set_star(ids, lvl)

    def schedule_save_state(self): self.save_timer.start()

    def save_window_state(self):
        # 使用 v7 Key 强制重置，修复Dock布局问题
        log.info("💾 保存窗口状态...")
        s = QSettings("ClipboardPro", "WindowState_v7")
        s.setValue("geometry", self.saveGeometry())
        s.setValue("windowState", self.dock_container.saveState())
        s.setValue("editMode", self.edit_mode)
        s.setValue("current_theme", self.current_theme)
        
        # 保存列宽
        widths = [self.table.columnWidth(i) for i in range(self.table.columnCount())]
        s.setValue("columnWidths", widths)
        
        # 保存列顺序
        header = self.table.horizontalHeader()
        visual_indices = [header.visualIndex(i) for i in range(self.table.columnCount())]
        s.setValue("columnOrder", visual_indices)
        
        # 保存对齐方式
        for i, align in self.col_alignments.items(): 
            s.setValue(f"col_{i}_align", align)
        
        # 保存置顶状态
        s.setValue("is_pinned", bool(self.windowFlags() & Qt.WindowStaysOnTopHint))
        
        # 保存每页显示数量
        s.setValue("pageSize", self.page_size)
        
        log.info("✅ 窗口状态已保存")

    def restore_window_state(self):
        log.info("💾 恢复窗口状态...")
        s = QSettings("ClipboardPro", "WindowState_v7")  # 使用v7
        
        if g := s.value("geometry"): 
            self.restoreGeometry(g)
            
        # 安全检查：如果恢复后的几何位置超出屏幕，则重置为安全大小
        # 这解决了“窗口太高超出屏幕”且无法缩小的问题
        screen_geo = QApplication.desktop().availableGeometry()
        curr_geo = self.geometry()
        
        # 如果高度超过屏幕高度，或者顶部/左侧超出可视范围
        if curr_geo.height() > screen_geo.height() or curr_geo.top() < 0 or curr_geo.left() < 0:
             log.warning("⚠️ 检测到窗口尺寸异常，正在重置为安全尺寸...")
             init_w = min(1200, int(screen_geo.width() * 0.9))
             init_h = min(700, int(screen_geo.height() * 0.9))
             self.resize(init_w, init_h)
             self.move((screen_geo.width() - init_w) // 2, (screen_geo.height() - init_h) // 2)

        if ws := s.value("windowState"):
            self.dock_container.restoreState(ws)
        else:
            # 如果没有保存的状态，则按比例设置默认宽度
            main_width = self.dock_container.width()
            left_width = int(main_width * 0.20)
            right_width = int(main_width * 0.25)
            
            # 获取所有左侧和右侧的Docks
            left_docks = [d for d in [self.dock_filter, self.dock_partition, self.dock_tags] if d.isVisible()]
            right_docks = [d for d in [self.dock_detail] if d.isVisible()]
            
            if left_docks:
                self.dock_container.resizeDocks(left_docks, [left_width] * len(left_docks), Qt.Horizontal)
            if right_docks:
                self.dock_container.resizeDocks(right_docks, [right_width] * len(right_docks), Qt.Horizontal)

        # 恢复置顶状态
        if s.value("is_pinned", False, type=bool):
            self.toggle_pin(True)
            if hasattr(self.title_bar, 'btn_pin'):
                self.title_bar.btn_pin.setChecked(True)

        # 强制显示面板，防止旧Bug导致隐藏
        self.dock_filter.setVisible(True)
        self.dock_partition.setVisible(True)
        self.dock_tags.setVisible(True)
        self.dock_detail.setVisible(True)
        
        # 关键修复：恢复状态后，重新应用允许停靠区域的限制
        # 彻底禁止停靠在上方和下方区域，仅保留左右停靠权限
        areas = Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
        self.dock_filter.setAllowedAreas(areas)
        self.dock_partition.setAllowedAreas(areas)
        self.dock_tags.setAllowedAreas(areas)
        self.dock_detail.setAllowedAreas(areas)
        
        self.edit_mode = s.value("editMode", False, type=bool)
        if hasattr(self.title_bar, 'btn_mode'): 
            self.title_bar.btn_mode.setChecked(self.edit_mode)
        self.toggle_edit_mode(self.edit_mode)

        # 恢复每页显示数量
        self.page_size = s.value("pageSize", 100, type=int)
        if hasattr(self, 'title_bar'):
            self.title_bar.set_display_count(self.page_size)
        
        # 恢复列宽
        if cw := s.value("columnWidths"):
            cw = [int(w) for w in cw]
            for i, w in enumerate(cw): 
                if i < self.table.columnCount(): 
                    self.table.setColumnWidth(i, w)  # 修复：columnWidth -> setColumnWidth
        
        # 恢复列顺序
        if col_order := s.value("columnOrder"):
            header = self.table.horizontalHeader()
            for logical_idx, visual_idx in enumerate(col_order):
                header.moveSection(header.visualIndex(logical_idx), int(visual_idx))  # 转换为整数
        
        log.info("✅ 窗口状态已恢复")
        for i in range(self.table.columnCount()):
            if align := s.value(f"col_{i}_align"): self.col_alignments[i] = int(align)
        theme = s.value("current_theme", "dark")
        self.apply_theme(theme)

    def handle_dock_visibility_changed(self, visible):
        """
        处理面板可见性变化（隐藏或拖出），确保中心区域优先扩张，而不是其他侧栏面板。
        """
        # 如果是变为不可见（拖出或关闭）
        if not visible:
            log.info("智能布局触发：侧栏变动，正在通过中心扩张回收空间...")
            
            # 记录当前剩余可见 Dock 的实际宽度（防止它们因为邻居消失突然变宽）
            left_docks = [d for d in [self.dock_filter, self.dock_partition, self.dock_tags] if d.isVisible() and not d.isFloating()]
            right_docks = [d for d in [self.dock_detail] if d.isVisible() and not d.isFloating()]
            
            # 使用 resizeDocks 维持现状（即不让它们变宽，从而迫使中间区域增大）
            # 延迟一小段时间执行，等待 Dock 状态真正平衡
            QTimer.singleShot(10, lambda: self._do_smart_resize(left_docks, right_docks))

    def _do_smart_resize(self, left_docks, right_docks):
        try:
            if left_docks:
                # 重新应用它们当前的宽度，防止其扩张
                widths = [d.width() for d in left_docks]
                self.dock_container.resizeDocks(left_docks, widths, Qt.Horizontal)
            if right_docks:
                widths = [d.width() for d in right_docks]
                self.dock_container.resizeDocks(right_docks, widths, Qt.Horizontal)
        except Exception as e:
            log.debug(f"智能布局调整略过: {e}")

    def closeEvent(self, e): self.save_window_state(); e.accept()

    def on_clipboard_event(self):
        """处理剪贴板变化事件，防止重复处理"""
        if self._processing_clipboard:
            return
        
        self._processing_clipboard = True
        try:
            mime = self.clipboard.mimeData()
            partition_info = self.partition_panel.get_current_selection()
            self.cm.process_clipboard(mime, partition_info)
        finally:
            self._processing_clipboard = False

    def refresh_after_capture(self):
        """捕获到新数据后，刷新主列表和分区面板"""
        # 使用 0ms 延迟确保当前事件处理完成后立即刷新 UI
        # 核心修复: 连接到具体的刷新方法，而不是全局刷新
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
        if self.page > 1: self.page -= 1; self.load_data()
    def next_page(self):
        if self.page * self.page_size < self.total_items: self.page += 1; self.load_data()

    def load_data(self, reset_page=False):
        try:
            log.info(f"🔄 开始加载数据 (reset_page={reset_page})")
            if reset_page: self.page = 1 # 保留以备将来使用
            
            tags = self.filter_panel.get_checked('tags')
            stars = self.filter_panel.get_checked('stars')
            colors = self.filter_panel.get_checked('colors')
            types = self.filter_panel.get_checked('types')
            date_filter = None
            date_opts = self.filter_panel.get_checked('date_create')
            if date_opts: date_filter = date_opts[0]
            
            date_modify_filter = None
            date_modify_opts = self.filter_panel.get_checked('date_modify')
            if date_modify_opts: date_modify_filter = date_modify_opts[0]
            
            search = self.title_bar.get_search_text()
            partition_filter = self.partition_panel.get_current_selection()
            
            # 新增逻辑：如果选择“今日数据”，则覆盖日期筛选器并清除分区筛选
            if partition_filter and partition_filter.get('type') == 'today':
                date_modify_filter = '今日'
                partition_filter = None  # 确保不按分区筛选

            # 彻底恢复多选功能：无论是否在回收站，均允许 ExtendedSelection (Shift/Ctrl+点击)
            self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
            
            if partition_filter and partition_filter.get('type') == 'trash':
                self.table.is_trash_view = True
            else:
                self.table.is_trash_view = False

            log.info(f"🔍 筛选条件: 星级={stars}, 颜色={colors}, 类型={types}, 标签={tags}, 创建日期={date_filter}, 修改日期={date_modify_filter}, 搜索={search}, 显示数量={self.page_size}")
            
            filters = {'stars': stars, 'colors': colors, 'types': types}
            
            # 获取总数
            self.total_items = self.db.get_count(filters=filters, search=search, selected_tags=tags, date_filter=date_filter, date_modify_filter=date_modify_filter, partition_filter=partition_filter)
            
            limit = self.page_size
            offset = 0

            # 模式判断
            if self.page_size != -1:
                # 分页模式
                self.bottom_bar.show() # 确保分页栏可见
                total_pages = (self.total_items + self.page_size - 1) // self.page_size if self.page_size > 0 else 1
                self.lbl_page.setText(f"{self.page} / {total_pages if total_pages > 0 else 1}")
                
                is_first_page = (self.page == 1)
                is_last_page = (self.page == total_pages) or (total_pages == 0)

                self.btn_first.setEnabled(not is_first_page)
                self.btn_prev.setEnabled(not is_first_page)
                self.btn_next.setEnabled(not is_last_page)
                self.btn_last.setEnabled(not is_last_page)

                offset = (self.page - 1) * self.page_size
            else:
                # 显示全部模式
                self.bottom_bar.show() # 确保分页栏可见
                limit = None # 无限制
                self.lbl_page.setText("1 / 1")
                self.btn_first.setEnabled(False)
                self.btn_prev.setEnabled(False)
                self.btn_next.setEnabled(False)
                self.btn_last.setEnabled(False)

            items = self.db.get_items(
                filters=filters, search=search, selected_tags=tags, 
                sort_mode=self.current_sort_mode,
                limit=limit, offset=offset, date_filter=date_filter, date_modify_filter=date_modify_filter,
                partition_filter=partition_filter
            )
            
            self.table.blockSignals(True)
            self.table.setRowCount(len(items))
            for row, item in enumerate(items):
                # ID列索引从9改为8
                self.table.setItem(row, 8, QTableWidgetItem(str(item.id)))
                
                # 状态列：显示颜色圆点和状态图标，不显示序号
                st_flags = ""
                if item.is_pinned: st_flags += "📌"
                if item.is_favorite: st_flags += "❤️"
                if item.is_locked: st_flags += "🔒"
                
                # 类型图标提取
                type_icon = ""
                if item.item_type == 'url':
                    type_icon = "🔗"
                elif item.item_type == 'image':
                    type_icon = "🖼️"
                elif item.item_type == 'file' and item.file_path:
                    if os.path.exists(item.file_path):
                        if os.path.isdir(item.file_path):
                            type_icon = "📂"
                        else:
                            ext = os.path.splitext(item.file_path)[1].lower()
                            if ext in ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma']:
                                type_icon = "🎵"
                            elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp']:
                                type_icon = "🖼️"
                            elif ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv']:
                                type_icon = "🎬"
                            else:
                                type_icon = "📄"
                    else:
                        type_icon = "📄" # 文件丢失
                        
                # 组合显示: 状态标记 + 类型图标
                # 优先显示类型图标，然后是状态
                display_text = f"{type_icon} {st_flags}".strip()
                
                state_item = QTableWidgetItem(display_text)
                if item.custom_color: state_item.setIcon(get_color_icon(item.custom_color))
                self.table.setItem(row, 0, state_item)  # 状态列（索引0）
                
                # 其他列（索引调整：移除了"序"列）
                self.table.setItem(row, 1, QTableWidgetItem(item.content.replace('\n', ' ')[:100]))  # 内容
                self.table.setItem(row, 2, QTableWidgetItem(item.note))  # 备注
                star_item = QTableWidgetItem("★" * item.star_level)
                # star_item.setForeground(QColor("#FFD700"))
                self.table.setItem(row, 3, star_item)  # 星级
                self.table.setItem(row, 4, QTableWidgetItem(format_size(item.content)))  # 大小
                if item.is_file and item.file_path:
                    _, ext = os.path.splitext(item.file_path)
                    type_str = ext.upper()[1:] if ext else "FILE"
                else: type_str = "TXT"
                self.table.setItem(row, 5, QTableWidgetItem(type_str))  # 类型
                self.table.setItem(row, 6, QTableWidgetItem(item.created_at.strftime("%m-%d %H:%M")))  # 创建时间
                
                # 设置对齐方式
                for col in range(7):  # 从8改为7（因为只有9列，隠藏了7,8）
                    align = self.col_alignments.get(col, Qt.AlignLeft | Qt.AlignVCenter if col in [1,2] else Qt.AlignCenter)
                    it = self.table.item(row, col)
                    if it: it.setTextAlignment(align)
            self.table.blockSignals(False)
            
            # --- 新的统计逻辑 ---
            # 1. 基于当前显示的 items 计算统计信息
            stats = self._calculate_stats_from_items(items)
            # 2. 更新筛选器面板
            self.filter_panel.update_stats(stats)
            
            # 标签面板和状态栏仍然使用全局信息
            self.tag_panel.refresh_tags(self.db)
            self.lbl_status.setText(f"总计: {self.total_items} 条 (当前显示: {len(items)} 条)")
            
            # 修复：检查是否有待高亮的项目
            if self.item_id_to_select_after_load is not None:
                self.select_item_in_table(self.item_id_to_select_after_load)
                self.item_id_to_select_after_load = None # 清空

        except Exception as e: log.error(f"Load Error: {e}", exc_info=True)

    def _calculate_stats_from_items(self, items):
        """根据给定的项目列表计算统计数据"""
        from data.database import Tag # 局部导入以避免循环依赖
        stats = {'tags': {}, 'stars': {}, 'colors': {}, 'types': {}}
        
        session = self.db.get_session()
        try:
            # 预加载所有标签以提高效率
            all_tags_in_db = {tag.name for tag in session.query(Tag).all()}

            for item in items:
                # 统计星级
                stats['stars'][item.star_level] = stats['stars'].get(item.star_level, 0) + 1
                
                # 统计颜色
                if item.custom_color:
                    stats['colors'][item.custom_color] = stats['colors'].get(item.custom_color, 0) + 1
                
                # 统计标签
                for tag in item.tags:
                    stats['tags'][tag.name] = stats['tags'].get(tag.name, 0) + 1

                # 统计类型 (与数据库中的逻辑保持一致)
                key = item.item_type
                if item.item_type == 'file' and item.file_path and os.path.exists(item.file_path):
                    if os.path.isdir(item.file_path):
                        key = 'folder'
                    else:
                        _, ext = os.path.splitext(item.file_path)
                        key = ext.lstrip('.').upper() if ext else 'FILE'
                elif item.item_type == 'image':
                    path = item.image_path or item.file_path
                    if path:
                        _, ext = os.path.splitext(path)
                        key = ext.lstrip('.').upper() if ext else 'IMAGE'
                    else:
                        key = 'IMAGE'
                
                if key not in ['text', 'url', 'folder']:
                    key = key.upper()
                
                stats['types'][key] = stats['types'].get(key, 0) + 1

        finally:
            session.close()
        
        # 转换标签格式以匹配 FilterPanel 的期望输入
        # 并确保数据库中存在但当前未显示的标签也以 0 的计数包含在内
        final_tags = {tag_name: 0 for tag_name in all_tags_in_db}

        final_tags.update(stats['tags'])
        stats['tags'] = list(final_tags.items())

        # 日期统计 (也基于当前 items)
        from datetime import datetime, time, timedelta
        
        def get_date_label(dt):
            today = datetime.now().date()
            if dt.date() == today: return "今日"
            if dt.date() == today - timedelta(days=1): return "昨日"
            if dt.date() >= today - timedelta(days=7): return "周内"
            if dt.date() >= today - timedelta(days=14): return "两周"
            if dt.month == today.month and dt.year == today.year: return "本月"
            
            first_day_current_month = today.replace(day=1)
            last_day_last_month = first_day_current_month - timedelta(days=1)
            first_day_last_month = last_day_last_month.replace(day=1)
            if first_day_last_month <= dt.date() <= last_day_last_month:
                return "上月"
            return None

        stats['date_create'] = {}
        stats['date_modify'] = {}
        for item in items:
            if label := get_date_label(item.created_at):
                stats['date_create'][label] = stats['date_create'].get(label, 0) + 1
            if item.modified_at:
                if label := get_date_label(item.modified_at):
                    stats['date_modify'][label] = stats['date_modify'].get(label, 0) + 1

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
            if it := self.table.item(row, col): it.setTextAlignment(align)
        self.schedule_save_state()

    def on_display_count_changed(self, count):
        """处理显示条数变化"""
        self.page_size = count
        self.load_data(reset_page=True)
        # self.schedule_save_state() # (可选) 如果需要保存这个设置

    def toggle_pin(self, checked):
        """窗口置顶功能 - 修复"""
        try:
            log.info(f"📌 切换窗口置顶状态: {checked}")
            
            # 使用 Qt 标准标志位而不是 Win32 API，兼容性更好
            # 注意: setWindowFlag 会隐藏窗口，需要重新 show()
            # 为了避免闪烁，通常需要小心处理，但在 Frameless 模式下，Qt 标志通常有效
            
            # 保留现有的 Flags (Frameless 等)
            current_flags = self.windowFlags()
            
            if checked:
                self.setWindowFlags(current_flags | Qt.WindowStaysOnTopHint)
            else:
                self.setWindowFlags(current_flags & ~Qt.WindowStaysOnTopHint)
            
            self.show()
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
        if checked: self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        else: self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.schedule_save_state()
    def on_table_double_click(self, item):
        if self.edit_mode: return
        self.copy_and_paste_item()
    def on_item_changed(self, item):
        if not self.edit_mode: return
        row = item.row()
        item_id = int(self.table.item(row, 9).text())
        if item.column() == 2: self.db.update_item(item_id, content=item.text().strip())
        elif item.column() == 3: self.db.update_item(item_id, note=item.text().strip())
    def copy_and_paste_item(self):
        if hasattr(self, 'current_item_id'):
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
                
                if self.last_external_hwnd:
                    self.showMinimized()
                    try:
                        ctypes.windll.user32.SetForegroundWindow(self.last_external_hwnd)
                        if ctypes.windll.user32.IsIconic(self.last_external_hwnd):
                            ctypes.windll.user32.ShowWindow(self.last_external_hwnd, 9)
                    except: pass
                    QTimer.singleShot(100, self._send_ctrl_v)
                else: self.statusBar().showMessage("✅ 已复制", 2000)
            session.close()
    def _send_ctrl_v(self):
        ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x56, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x56, 2, 0)
        ctypes.windll.user32.keybd_event(0x11, 2, 0)
    def update_detail_panel(self):
        rows = self.table.selectionModel().selectedRows()

        # 核心逻辑：根据是否有选中行，更新左侧标签面板的可用状态
        has_selection = bool(rows)
        self.tag_panel.setEnabled(has_selection)
        # DetailPanel 的交互组件状态由其内部的 load_item/clear 自动切换

        if not rows:
            self.detail_panel.clear()
            return
        
        # 添加空值检查，修复ID列索引
        item = self.table.item(rows[0].row(), 8)
        if not item or not item.text():
            log.warning("⚠️ 选中行的ID列为空")
            return
        
        item_id = int(item.text())
        log.debug(f"📋 更新详情面板，项目ID: {item_id}")
        session = self.db.get_session()
        from data.database import ClipboardItem
        # 修复: 移除对旧的 Partition.group 的 joinedload
        item_obj = session.query(ClipboardItem).options(
            joinedload(ClipboardItem.tags),
            joinedload(ClipboardItem.partition) # 只加载直接关联的 partition
        ).get(item_id)
        
        if item_obj:
            tags = [t.name for t in item_obj.tags]
            
            # 新逻辑: 递归获取分区路径
            path_parts = []
            current_partition = item_obj.partition
            while current_partition:
                path_parts.append(current_partition.name)
                # 在循环内继续查询父级
                current_partition = session.query(Partition).get(current_partition.parent_id)

            path_parts.reverse() # 反转得到 "父 -> 子" 的顺序
            
            group_name = path_parts[0] if path_parts else None
            partition_name = " -> ".join(path_parts) if path_parts else None

            self.detail_panel.load_item(
                item_obj.content, item_obj.note, tags,
                group_name=group_name,
                partition_name=partition_name,
                item_type=item_obj.item_type,
                image_path=item_obj.image_path,
                file_path=item_obj.file_path,
                image_blob=item_obj.data_blob
            )
            self.current_item_id = item_id
        session.close()
    def reorder_items(self, new_ids): self.db.update_sort_order(new_ids)
    def save_note(self, text):
        if hasattr(self, 'current_item_id'): self.db.update_item(self.current_item_id, note=text); self.load_data()
    
    def on_tags_added(self, tags):
        """处理详细信息面板提交的标签列表"""
        if hasattr(self, 'current_item_id') and self.current_item_id:
            # 批量添加标签到当前选中的项目
            self.db.add_tags_to_items([self.current_item_id], tags)
            self.update_detail_panel() # 刷新详细信息面板
            self.load_data()           # 刷新主列表
            self.partition_panel.refresh_partitions() # 刷新分区面板以更新计数

    def on_tag_panel_commit_tags(self, tags):
        """处理左侧标签面板提交的标签，为所有选中项批量添加"""
        rows = self.table.selectionModel().selectedRows()
        if not rows or not tags:
            return
        
        item_ids = []
        for r in rows:
            item = self.table.item(r.row(), 8)
            if item and item.text():
                item_ids.append(int(item.text()))
        
        if item_ids:
            self.db.add_tags_to_items(item_ids, tags)
            self.load_data()
            self.update_detail_panel()
            self.partition_panel.refresh_partitions() # 刷新分区面板以更新计数
            log.info(f"✅ 已为 {len(item_ids)} 个项目批量添加标签: {tags}")

    def remove_tag(self, tag):
        if hasattr(self, 'current_item_id'): 
            self.db.remove_tag_from_item(self.current_item_id, tag)
            self.update_detail_panel()
            self.load_data()
            self.partition_panel.refresh_partitions() # 刷新分区面板以更新计数
    def toggle_theme(self):
        if self.current_theme == "dark": self.apply_theme("light")
        else: self.apply_theme("dark")
    def apply_theme(self, name):
        self.current_theme = name
        app = QApplication.instance()
        if name == "dark":
            app.setStyleSheet(themes.dark.STYLESHEET)
        else:
            # Fallback to dark theme if light theme is requested but not available
            app.setStyleSheet(themes.dark.STYLESHEET)
    
    # 颜色设置方法
    def toolbar_set_color(self):
        """从标题栏颜色按钮设置选中项的颜色"""
        log.info("🌈 颜色设置按钮被点击")
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            log.warning("⚠️ 未选中任何项目，忽略颜色设置请求")
            # 用户要求"弄没了"，移除弹窗
            return
        
        item_ids = []
        for r in rows:
            item = self.table.item(r.row(), 8)
            if item and item.text():
                item_ids.append(int(item.text()))
        log.info(f"✅ 选中 {len(item_ids)} 个项目，ID: {item_ids}")
        if item_ids:
            self.set_custom_color(item_ids)
        else:
            log.error("❌ 所有选中项的ID列都为空")

    def set_custom_color(self, item_ids):
        """打开颜色选择对话框"""
        log.info(f"🎨 打开颜色选择器，项目ID: {item_ids}")
        # from color_selector import ColorSelectorDialog
        dlg = ColorSelectorDialog(self)
        if dlg.exec_():
            if dlg.selected_color:
                log.info(f"✅ 用户选择颜色: {dlg.selected_color}")
                self.batch_set_color(item_ids, dlg.selected_color)
            else:
                log.info("🗑️ 用户选择清除颜色")
                self.batch_set_color(item_ids, "")
        else:
            log.info("❌ 用户取消颜色选择")

    def batch_set_color(self, ids, clr):
        """批量设置颜色"""
        log.info(f"🎯 开始批量设置颜色，ID: {ids}, 颜色: {clr}")
        session = self.db.get_session()
        try:
            from data.database import ClipboardItem
            count = 0
            for item_id in ids:
                if item := session.query(ClipboardItem).get(item_id):
                    item.custom_color = clr
                    count += 1
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
        """在右侧主表格中查找并高亮指定的项目ID"""
        log.debug(f"滚动到项目: {item_id_to_select}")
        # ID 在第 9 列，索引 8
        id_column_index = 8
        for row in range(self.table.rowCount()):
            item = self.table.item(row, id_column_index)
            if item and item.text() == str(item_id_to_select):
                # 找到了匹配的行
                self.table.blockSignals(True)
                self.table.selectRow(row)
                self.table.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
                self.table.blockSignals(False)
                log.info(f"✅ 已在表格中高亮显示项目 {item_id_to_select}")
                return
        log.warning(f"⚠️ 未能在当前显示的表格中找到项目ID: {item_id_to_select}")
    
    def on_tag_panel_add_tag(self, tag_input=None):
        """
        处理标签添加
        tag_input: 可能是单个字符串，也可能是字符串列表(新控件传过来的)
        """
        if not tag_input:
            # 兼容旧逻辑：如果参数为空，弹出对话框
            dlg = TagDialog(self.db, self)
            if dlg.exec_(): self.tag_panel.refresh_tags(self.db)
            return

        # 统一转为列表处理
        tags_to_add = tag_input if isinstance(tag_input, list) else [tag_input]
        
        session = self.db.get_session()
        from data.database import Tag
        try:
            has_new = False
            for tag_name in tags_to_add:
                tag_name = tag_name.strip()
                if not tag_name: continue
                
                # 检查是否存在
                if not session.query(Tag).filter_by(name=tag_name).first():
                    session.add(Tag(name=tag_name))
                    has_new = True
            
            if has_new:
                session.commit()
                self.tag_panel.refresh_tags(self.db)
                log.info(f"✅ 批量添加标签: {tags_to_add}")
        except Exception as e:
            log.error(f"添加标签失败: {e}")
        finally:
            session.close()
    
    def on_tag_selected(self, tag_name):
        """标签面板选中标签"""
        log.info(f"🏷️ 标签被选中: {tag_name}")
        # 可以实现点击标签自动筛选的功能
        # 这里暂时不实现，因为筛选器已经有标签筛选了

    def handle_item_selection_in_partition(self, item_id):
        """处理来自侧边栏的项选择，以便在加载后高亮显示"""
        log.debug(f"接收到侧边栏高亮请求，项目ID: {item_id}，将在加载后处理。")
        self.item_id_to_select_after_load = item_id