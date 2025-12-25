# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (QTableWidget, QAbstractItemView, QLineEdit, QWidget,
                             QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem,
                             QFrame, QLabel, QCompleter, QComboBox, QToolButton, QMenu, QStyledItemDelegate, QStyle)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings, QSize, QEvent, QRect, QStringListModel
from PyQt5.QtGui import QColor, QBrush, QIcon, QPen, QFontMetrics
from core.shared import get_color_icon

# === 侧边栏 ===
class FilterTreeWidget(QTreeWidget):
    filterChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setObjectName("FilterTree") # 设置ObjectName
        self.itemChanged.connect(lambda: self.filterChanged.emit())
        
        self.roots = {}
        order = [
            ('stars', '⭐ 评级'),
            ('colors', '🎨 颜色'),
            ('tags', '🏷️ 标签'),
            ('date_create', '📅 创建日期'),
            ('date_modify', '📅 修改日期')
        ]
        
        for key, label in order:
            item = QTreeWidgetItem(self)
            item.setText(0, label)
            item.setExpanded(True)
            item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            self.roots[key] = item
            
        self._add_fixed_date_options('date_create')
        self._add_fixed_date_options('date_modify')

    def _add_fixed_date_options(self, key):
        root = self.roots[key]
        options = ["今日", "昨日", "周内", "两周", "本月", "上月", "自定义"]
        for opt in options:
            child = QTreeWidgetItem(root)
            child.setText(0, opt)
            child.setData(0, Qt.UserRole, opt)
            child.setCheckState(0, Qt.Unchecked)

    def update_stats(self, stats):
        self.blockSignals(True)
        
        star_data = []
        for i in range(5, 0, -1):
            label = "★" * i
            count = stats['stars'].get(i, 0)
            star_data.append((i, label, count))
        
        if 0 in stats['stars']:
            star_data.append((0, "无", stats['stars'][0]))

        self._refresh('stars', star_data)
        self._refresh('colors', [(c, c.upper(), count) for c, count in stats['colors'].items()], is_col=True)
        self._refresh('tags', stats.get('tags', []), is_tag=True)
        self.blockSignals(False)

    def _refresh(self, key, data, is_tag=False, is_col=False):
        root = self.roots[key]
        checked = {root.child(i).data(0, Qt.UserRole) for i in range(root.childCount()) if root.child(i).checkState(0) == Qt.Checked}
        root.takeChildren()
        
        if not data:
            empty = QTreeWidgetItem(root)
            empty.setText(0, "暂无")
            empty.setFlags(Qt.NoItemFlags)
            return

        for v, l, c in data:
            if is_tag: v, l, c = v, v, l
            if c == 0 and v not in checked: continue
            child = QTreeWidgetItem(root); child.setText(0, f"{l} ({c})"); child.setData(0, Qt.UserRole, v)
            child.setCheckState(0, Qt.Checked if v in checked else Qt.Unchecked)
            if is_col: child.setIcon(0, get_color_icon(v))

    def get_checked(self, key):
        root = self.roots[key]
        return [root.child(i).data(0, Qt.UserRole) for i in range(root.childCount()) if root.child(i).checkState(0) == Qt.Checked]

# === 表格 ===
class DraggableTable(QTableWidget):
    reorder_signal = pyqtSignal(list)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True); self.setAcceptDrops(True); self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionBehavior(QAbstractItemView.SelectRows); self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setShowGrid(False); self.setAlternatingRowColors(True)

    def dropEvent(self, event):
        if event.source() != self: super().dropEvent(event); return
        super().dropEvent(event)
        new_ids = []
        for r in range(self.rowCount()):
            item = self.item(r, 9)
            if item: new_ids.append(int(item.text()))
        self.reorder_signal.emit(new_ids)

# === 搜索框 ===

class HistoryCompleterDelegate(QStyledItemDelegate):
    """自定义委托，用于在搜索历史记录的末尾绘制一个删除按钮。"""
    delete_triggered = pyqtSignal(str)

    def paint(self, painter, option, index):
        # 首先调用父类的paint方法，绘制背景、文本等基本元素
        super().paint(painter, option, index)

        # 获取删除按钮的矩形区域
        delete_button_rect = self.get_delete_button_rect(option)

        painter.save()

        # 如果鼠标悬停在该项上，则高亮删除按钮
        if option.state & QStyle.State_MouseOver:
            pen = QPen(QColor("#d0d0d0"))  # 悬停时使用更亮的灰色
        else:
            pen = QPen(QColor("#a0a0a0"))  # 默认使用暗灰色

        painter.setPen(pen)

        # 设置字体以绘制 "×"
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)

        # 在计算好的矩形区域内居中绘制 "×"
        painter.drawText(delete_button_rect, Qt.AlignCenter, "×")
        painter.restore()

    def editorEvent(self, event, model, option, index):
        # 仅在鼠标释放事件时响应
        if event.type() == QEvent.MouseButtonRelease:
            # 检查点击位置是否在删除按钮的矩形区域内
            if self.get_delete_button_rect(option).contains(event.pos()):
                # 发射信号，通知SearchBar删除此项
                self.delete_triggered.emit(index.data())
                return True  # 返回True表示事件已被处理
        return super().editorEvent(event, model, option, index)

    def get_delete_button_rect(self, option):
        """计算并返回删除按钮 "×" 的矩形区域。"""
        rect = option.rect
        # 按钮位于最右侧，宽度为20px
        delete_button_rect = QRect(rect.right() - 20, rect.top(), 20, rect.height())
        return delete_button_rect

class SearchBar(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("🔍 搜索内容...")
        self.settings = QSettings("ClipboardPro", "SearchHistory")
        self.history = self.settings.value("history", [], type=list)

        # 使用 QStringListModel 来管理历史记录
        self.model = QStringListModel(self.history)
        
        self.completer = QCompleter(self.model, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        
        # 实例化并应用自定义委托
        self.delegate = HistoryCompleterDelegate(self)
        self.completer.popup().setItemDelegate(self.delegate)

        self.setCompleter(self.completer)
        self.returnPressed.connect(self._save)

        # 连接委托的删除信号到删除槽函数
        self.delegate.delete_triggered.connect(self.delete_history_item)
        
        self.clearBtn = QPushButton("×", self)
        self.clearBtn.setCursor(Qt.PointingHandCursor)
        self.clearBtn.setFixedSize(20, 20)
        self.clearBtn.setObjectName("SearchBarClearButton") # 设置ObjectName
        self.clearBtn.clicked.connect(self.clear)
        self.clearBtn.hide()
        self.textChanged.connect(self._on_text_changed)
        
        # 为输入框设置右边距，防止文本与清除按钮重叠
        # 按钮宽度为20px, 与边框的距离为11px, 再额外加4px的文本间距
        self.setTextMargins(0, 0, 20 + 11 + 4, 0)

    def _on_text_changed(self, text):
        self.clearBtn.setVisible(bool(text))

    def resizeEvent(self, event):
        button_size = self.clearBtn.sizeHint()
        frame_rect = self.rect()
        # 将按钮放置在最右侧，并保留11px的边距 (4px原边距 + 7px左移)
        x_pos = frame_rect.right() - button_size.width() - 11
        # 垂直居中
        y_pos = (frame_rect.height() - button_size.height()) // 2
        self.clearBtn.move(x_pos, y_pos)
        super().resizeEvent(event)

    def delete_history_item(self, text):
        """从历史记录中删除指定的项。"""
        if text in self.history:
            self.history.remove(text)
            self.settings.setValue("history", self.history)
            # 更新模型以刷新视图
            self.model.setStringList(self.history)

    def _save(self):
        """保存新的搜索记录。"""
        t = self.text().strip()
        if t and t not in self.history:
            self.history.insert(0, t)
            self.history = self.history[:20]  # 限制历史记录数量
            self.settings.setValue("history", self.history)
            # 更新模型以刷新视图
            self.model.setStringList(self.history)

# === 标题栏 ===
class CustomTitleBar(QWidget):
    refresh_clicked = pyqtSignal()
    theme_clicked = pyqtSignal()
    search_changed = pyqtSignal()
    clean_clicked = pyqtSignal()
    color_clicked = pyqtSignal()
    pin_clicked = pyqtSignal(bool)
    mode_clicked = pyqtSignal(bool)
    display_count_changed = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 0, 0)
        layout.setSpacing(6)
        
        title = QLabel("💾 印象记忆")
        title.setObjectName("WindowTitle") # 设置ObjectName
        layout.addWidget(title)
        
        layout.addSpacing(20) # 增加 20px 的右偏移
        
        self.search_bar = SearchBar()
        self.search_bar.setObjectName("ToolbarSearchBar") # 为搜索框设置对象名，以便单独控制高度
        self.search_bar.setFixedWidth(220)
        self.search_bar.textChanged.connect(lambda: self.search_changed.emit())
        self.search_bar.returnPressed.connect(lambda: self.search_changed.emit())
        layout.addWidget(self.search_bar)
        
        self.btn_display_count = QToolButton()
        self.btn_display_count.setText("显示: 100")
        self.btn_display_count.setPopupMode(QToolButton.InstantPopup)
        self.btn_display_count.setIconSize(QSize(12, 12))
        self.btn_display_count.setObjectName("DisplayCountButton") # 设置ObjectName
        
        menu = QMenu(self)
        counts = ["显示条数", 100, 200, 300, 400, 500, 1000]
        for count in counts:
            action = menu.addAction(str(count))
            action.setData(count if isinstance(count, int) else -1)
        
        menu.triggered.connect(self._on_display_count_changed)
        self.btn_display_count.setMenu(menu)
        layout.addWidget(self.btn_display_count)
        
        layout.addStretch()
        
        self.btn_clean = self._btn("🗑️", "清理"); self.btn_clean.setObjectName("ToolBarButton"); self.btn_clean.clicked.connect(self.clean_clicked.emit); layout.addWidget(self.btn_clean)
        self.btn_refresh = self._btn("🔄", "刷新"); self.btn_refresh.setObjectName("ToolBarButton"); self.btn_refresh.clicked.connect(self.refresh_clicked.emit); layout.addWidget(self.btn_refresh)
        self.btn_color = self._btn("🌈", "设置标签颜色"); self.btn_color.setObjectName("ToolBarButton"); self.btn_color.clicked.connect(self.color_clicked.emit); layout.addWidget(self.btn_color)
        self.btn_mode = self._btn("📝", "编辑模式", True); self.btn_mode.setObjectName("ToolBarButton"); self.btn_mode.clicked.connect(self.mode_clicked.emit); layout.addWidget(self.btn_mode)
        self.btn_pin = self._btn("📌", "置顶", True); self.btn_pin.setObjectName("ToolBarButton"); self.btn_pin.clicked.connect(self.pin_clicked.emit); layout.addWidget(self.btn_pin)

        self.btn_settings = QToolButton()
        self.btn_settings.setText("⚙️")
        self.btn_settings.setPopupMode(QToolButton.InstantPopup)
        self.btn_settings.setObjectName("ToolBarButton") # 恢复通用ID以保持样式统一
        self.btn_settings.setProperty("class", "no-arrow") # 添加自定义属性用于精确控制
        
        settings_menu = QMenu(self)
        theme_action = settings_menu.addAction("切换主题")
        theme_action.triggered.connect(self.theme_clicked.emit)
        
        self.reset_layout_action = settings_menu.addAction("恢复默认布局")
        
        self.btn_settings.setMenu(settings_menu)
        layout.addWidget(self.btn_settings)
        
        line = QFrame(); line.setFrameShape(QFrame.VLine); line.setFrameShadow(QFrame.Sunken); line.setFixedHeight(20); line.setObjectName("TitleBarSeparator")
        layout.addWidget(line)
        
        self.btn_min = self._win_btn("—"); self.btn_min.setObjectName("WindowControlButton"); self.btn_min.clicked.connect(self.window().showMinimized); layout.addWidget(self.btn_min)
        self.btn_max = self._win_btn("⬜"); self.btn_max.setObjectName("WindowControlButton"); self.btn_max.clicked.connect(self.toggle_max); layout.addWidget(self.btn_max)
        self.btn_close = self._win_btn("✕", True); self.btn_close.setObjectName("WindowCloseButton"); self.btn_close.clicked.connect(self.window().close); layout.addWidget(self.btn_close)

    def _on_display_count_changed(self, action):
        count = action.data()
        self._update_display_count_text(count)
        self.display_count_changed.emit(count)

    def _update_display_count_text(self, count):
        if count == -1:
            self.btn_display_count.setText("显示条数")
        else:
            self.btn_display_count.setText(f"显示: {count}")

    def set_display_count(self, count):
        self._update_display_count_text(count)
    
    def _btn(self, t, tip, chk=False):
        b = QPushButton(t); b.setToolTip(tip); b.setFixedSize(30, 30)
        if chk:
            b.setCheckable(True)
        return b

    def _win_btn(self, t, cls=False):
        b = QPushButton(t)
        b.setFixedSize(30, 30)
        return b

    def toggle_max(self):
        w = self.window()
        if w.isMaximized(): w.showNormal(); self.btn_max.setText("⬜")
        else: w.showMaximized(); self.btn_max.setText("❐")
            
    def get_search_text(self): return self.search_bar.text().strip()
