# -*- coding: utf-8 -*-
import os
from PyQt5.QtWidgets import QTableWidget, QAbstractItemView, QHeaderView, QTableWidgetItem
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from core.shared import get_color_icon, format_size

class TablePanel(QTableWidget):
    reorder_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_trash_view = False
        
        # 基础设置
        self.setColumnCount(9)
        self.setHorizontalHeaderLabels(["状态", "内容", "备注", "星级", "大小", "类型", "创建时间", "PATH", "ID"])
        self.hideColumn(7) # 隐藏 PATH
        self.hideColumn(8) # 隐藏 ID
        
        # === 核心修复：行高与图标 ===
        # 1. 强制设定行高，不再依赖自动计算，解决挤压问题
        self.verticalHeader().setDefaultSectionSize(38) 
        # 2. 限制图标尺寸，防止图片过大撑满行
        self.setIconSize(QSize(22, 22)) 
        # 3. 设置状态列宽
        self.setColumnWidth(0, 50) 
        
        # 样式与交互
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setShowGrid(False) # 不显示网格线
        self.setAlternatingRowColors(True) # 斑马纹
        self.setFocusPolicy(Qt.StrongFocus)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # 表头交互
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.setSectionsMovable(True)
        
        # 垂直表头（行号）
        self.verticalHeader().setVisible(True)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed) # 固定行高，防止自动塌缩
        self.verticalHeader().setDefaultAlignment(Qt.AlignCenter)

        # 监听 Viewport (滚轮事件)
        self.viewport().installEventFilter(self)
        
        # 加载字体设置
        self.load_font_settings()

    def load_font_settings(self):
        from PyQt5.QtCore import QSettings
        settings = QSettings("ClipboardPro", "Settings")
        size = settings.value("table_font_size", 10, type=int)
        font = self.font()
        font.setPointSize(size)
        self.setFont(font)
        # 根据字体调整行高，最小 38px
        self.verticalHeader().setDefaultSectionSize(max(38, size + 20))

    def eventFilter(self, source, event):
        if source == self.viewport() and event.type() == event.Wheel:
            if event.modifiers() == Qt.ControlModifier:
                delta = event.angleDelta().y()
                self.handle_zoom(delta)
                return True
            # 防止触摸板水平漂移
            if abs(event.angleDelta().x()) > abs(event.angleDelta().y()):
                return True
        return super().eventFilter(source, event)

    def handle_zoom(self, delta):
        font = self.font()
        size = font.pointSize()
        if delta > 0: size += 1
        else: size = max(8, size - 1)
        font.setPointSize(size)
        self.setFont(font)
        # 缩放时同步调整行高
        self.verticalHeader().setDefaultSectionSize(size + 20)
        
        from PyQt5.QtCore import QSettings
        QSettings("ClipboardPro", "Settings").setValue("table_font_size", size)

    def startDrag(self, supportedActions):
        from PyQt5.QtWidgets import QDrag
        from PyQt5.QtGui import QPixmap, QPainter, QFont, QColor
        from PyQt5.QtCore import QPoint

        selected_rows = self.selectionModel().selectedRows()
        if not selected_rows:
            return

        drag = QDrag(self)
        mime = self.mimeData(self.selectedIndexes())
        drag.setMimeData(mime)

        # 创建自定义预览图
        pixmap = self._create_drag_pixmap(selected_rows)
        drag.setPixmap(pixmap)

        # 设置热点为左下角
        drag.setHotSpot(pixmap.rect().bottomLeft())

        drag.exec_(supportedActions)

    def _create_drag_pixmap(self, selected_rows):
        """根据选中的行创建拖拽预览图"""
        from PyQt5.QtGui import QPixmap, QPainter, QFont, QColor, QLinearGradient
        from PyQt5.QtCore import QRect, QRectF

        # 基础尺寸和样式
        width, height = 300, 60
        font_name = "Microsoft YaHei"
        base_font_size = 9

        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)

        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)

        # 背景
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, width-1, height-1), 8, 8)

        grad = QLinearGradient(0, 0, 0, height)
        grad.setColorAt(0, QColor(60, 60, 65))
        grad.setColorAt(1, QColor(40, 40, 45))

        p.setPen(QPen(QColor(100, 100, 100), 1))
        p.fillPath(path, grad)
        p.drawPath(path)

        # 获取第一行的数据
        first_row = selected_rows[0].row()
        icon_item = self.item(first_row, 0)
        content_item = self.item(first_row, 1)
        note_item = self.item(first_row, 2)

        # 绘制图标和状态
        if icon_item:
            icon_pixmap = icon_item.icon().pixmap(18, 18)
            p.drawPixmap(10, 10, icon_pixmap)
            p.setFont(QFont(font_name, base_font_size + 2))
            p.setPen(QColor(220, 220, 220))
            p.drawText(QRect(35, 10, 30, 20), Qt.AlignLeft | Qt.AlignVCenter, icon_item.text())

        # 绘制内容
        if content_item:
            p.setFont(QFont(font_name, base_font_size, QFont.Bold))
            p.setPen(QColor(240, 240, 240))
            p.drawText(QRect(10, 30, width - 20, 15), Qt.AlignLeft | Qt.AlignVCenter, content_item.text())

        # 绘制备注
        if note_item:
            p.setFont(QFont(font_name, base_font_size))
            p.setPen(QColor(180, 180, 180))
            p.drawText(QRect(10, 45, width - 20, 15), Qt.AlignLeft | Qt.AlignVCenter, note_item.text())

        # 绘制角标
        if len(selected_rows) > 1:
            p.setFont(QFont(font_name, 8, QFont.Bold))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 120, 215))
            p.drawRoundedRect(width-32, height-20, 28, 16, 8, 8)
            p.setPen(Qt.white)
            p.drawText(QRect(width-32, height-20, 28, 16), Qt.AlignCenter, f"+{len(selected_rows)}")

        p.end()
        return pixmap

    def dropEvent(self, event):
        if event.source() != self: 
            super().dropEvent(event)
            return
        super().dropEvent(event)
        new_ids = []
        for r in range(self.rowCount()):
            item = self.item(r, 8)
            if item: new_ids.append(int(item.text()))
        self.reorder_signal.emit(new_ids)

    def mimeData(self, indexes):
        from PyQt5.QtCore import QMimeData
        mime_data = QMimeData()
        item_ids = []
        unique_rows = {index.row() for index in indexes}
        for row in unique_rows:
            id_item = self.item(row, 8)
            if id_item: item_ids.append(id_item.text())
        if item_ids:
            encoded_data = ",".join(item_ids).encode()
            mime_data.setData("application/x-clipboard-item-ids", encoded_data)
            if self.is_trash_view:
                mime_data.setData("application/x-clipboard-source", b"trash")
        return mime_data

    def populate_table(self, items, col_alignments):
        """填充表格数据，这是 MainWindow 调用的核心方法"""
        self.blockSignals(True)
        self.setRowCount(len(items))
        
        for row, item in enumerate(items):
            # ID (Hidden)
            self.setItem(row, 8, QTableWidgetItem(str(item.id)))
            
            # 状态与图标
            st_flags = ""
            if item.is_pinned: st_flags += "📌"
            if item.is_favorite: st_flags += "❤️"
            if item.is_locked: st_flags += "🔒"
            
            type_icon = self._get_type_symbol(item)
            display_text = f"{type_icon} {st_flags}".strip()
            
            state_item = QTableWidgetItem(display_text)
            if item.custom_color:
                state_item.setIcon(get_color_icon(item.custom_color))
            # 文本居中
            state_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 0, state_item)
            
            # 内容
            content_display = self._get_content_display(item)
            content_item = QTableWidgetItem(content_display)
            content_item.setToolTip(item.content[:500]) # 限制Tooltip长度防止卡顿
            self.setItem(row, 1, content_item)

            # 其他
            self.setItem(row, 2, QTableWidgetItem(item.note))
            self.setItem(row, 3, QTableWidgetItem("★" * item.star_level))
            self.setItem(row, 4, QTableWidgetItem(format_size(item.content)))
            self.setItem(row, 5, QTableWidgetItem(self._get_type_string(item)))
            self.setItem(row, 6, QTableWidgetItem(item.created_at.strftime("%m-%d %H:%M")))
            
            # 应用对齐方式
            for col in range(7):
                # 默认: 内容(1)和备注(2)左对齐，其他居中
                default_align = Qt.AlignLeft | Qt.AlignVCenter if col in [1, 2] else Qt.AlignCenter
                align = col_alignments.get(col, default_align)
                
                it = self.item(row, col)
                if it: it.setTextAlignment(align)

        self.blockSignals(False)

    def _get_content_display(self, item):
        if item.item_type == 'file' and item.file_path:
            return os.path.basename(item.file_path)
        elif item.item_type == 'url' and item.url_domain:
            return f"[{item.url_domain}] {item.url_title or ''}"
        elif item.item_type == 'image':
            return "[图片] " + (os.path.basename(item.image_path) if item.image_path else "")
        else:
            return item.content.replace('\n', ' ').replace('\r', '').strip()[:150]

    def _get_type_symbol(self, item):
        if item.item_type == 'url': return "🔗"
        if item.item_type == 'image': return "🖼️"
        if item.item_type == 'file': return "📂" if os.path.isdir(item.file_path or "") else "📄"
        return "📝"

    def _get_type_string(self, item):
        if item.item_type == 'file' and item.file_path:
            _, ext = os.path.splitext(item.file_path)
            return ext.upper()[1:] if ext else "FILE"
        return "TXT"