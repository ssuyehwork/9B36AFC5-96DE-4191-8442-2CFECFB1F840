# -*- coding: utf-8 -*-
import logging
import random
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QMenu, QInputDialog, QMessageBox, QLineEdit, QColorDialog,
                             QAbstractItemView, QStyle, QTreeWidgetItemIterator)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPixmap, QColor, QPainter

log = logging.getLogger(__name__)


class PartitionTreeWidget(QTreeWidget):
    """一个支持层级分区拖放的 QTreeWidget 子类。"""
    partitionsUpdated = pyqtSignal()

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setIndentation(20) # 恢复缩进
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSortingEnabled(False)
        self.setFocusPolicy(Qt.NoFocus) # 彻底禁用焦点框显示
        self.setRootIsDecorated(True) # 恢复装饰线
        self.setAllColumnsShowFocus(True) # 关键：让高亮横跨全行

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            if selected_item := self.currentItem():
                self.parent()._delete_item(selected_item)
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-clipboard-item-ids"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        target_item = self.itemAt(event.pos())
        if not target_item:
            event.ignore(); return
        
        target_data = target_item.data(0, Qt.UserRole)
        if not target_data:
            event.ignore(); return
        
        target_type = target_data.get('type')
        
        # 外部拖拽：项目可以被拖到任何分区或回收站
        if event.mimeData().hasFormat("application/x-clipboard-item-ids"):
            if target_type in ['partition', 'trash']:
                event.acceptProposedAction()
            else:
                event.ignore()
        # 内部拖拽：分区可以被拖到其他分区（成为子分区）或回收站
        else:
            dragged_item = self.currentItem()
            if not dragged_item:
                event.ignore(); return
            
            dragged_data = dragged_item.data(0, Qt.UserRole)
            if not dragged_data or dragged_data.get('type') != 'partition':
                event.ignore(); return
            
            # 阻止将一个分区拖放到它自己的子孙分区中
            if self._is_descendant(dragged_item, target_item):
                event.ignore(); return

            if target_type in ['partition', 'trash']:
                event.acceptProposedAction()
            else:
                super().dragMoveEvent(event)

    def dropEvent(self, event):
        target_item = self.itemAt(event.pos())
        if not target_item:
            event.ignore(); return
        target_data = target_item.data(0, Qt.UserRole)
        if not target_data:
            event.ignore(); return
        target_type = target_data.get('type')

        # --- 处理从外部表格拖拽过来的项目 ---
        if event.mimeData().hasFormat("application/x-clipboard-item-ids"):
            encoded_data = event.mimeData().data("application/x-clipboard-item-ids")
            item_ids = [int(id_str) for id_str in encoded_data.data().decode().split(',') if id_str]
            if not item_ids:
                event.ignore(); return

            if target_type == 'trash':
                self.db.move_items_to_trash(item_ids)
            elif target_type == 'partition':
                partition_id = target_data.get('id')
                is_from_trash = event.mimeData().data("application/x-clipboard-source") == b"trash"
                if is_from_trash:
                    self.db.restore_and_move_items(item_ids, partition_id)
                else:
                    self.db.move_items_to_partition(item_ids, partition_id)
            else:
                event.ignore(); return

            self.partitionsUpdated.emit()
            event.acceptProposedAction()
        # --- 处理内部拖拽分区 ---
        else:
            dragged_item = self.currentItem()
            if not dragged_item:
                event.ignore(); return

            if target_type == 'trash':
                self.parent()._delete_item(dragged_item)
            else:
                super().dropEvent(event) # 让QTreeWidget处理UI移动
                self._update_partitions_from_tree_state()

    def _update_partitions_from_tree_state(self):
        """遍历整个树，并将新的层级结构和顺序持久化到数据库中"""
        def process_children(parent_item, parent_id_in_db):
            for i in range(parent_item.childCount()):
                item = parent_item.child(i)
                data = item.data(0, Qt.UserRole)
                if data and data.get('type') == 'partition':
                    partition_id = data['id']
                    self.db.update_partition(partition_id, parent_id=parent_id_in_db, sort_index=float(i))
                    process_children(item, partition_id)

        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            data = item.data(0, Qt.UserRole)
            # 只处理用户创建的分区，跳过静态项
            if data and data.get('type') == 'partition':
                partition_id = data['id']
                self.db.update_partition(partition_id, parent_id=None, sort_index=float(i))
                process_children(item, partition_id)
        
        log.info("分区结构和顺序已通过拖放更新。")
        self.partitionsUpdated.emit()
        
    def _is_descendant(self, potential_parent, potential_child):
        """检查 potential_child 是否是 potential_parent 的子孙"""
        parent = potential_child.parent()
        while parent:
            if parent == potential_parent:
                return True
            parent = parent.parent()
        return False

class PartitionPanel(QWidget):
    """分区管理面板"""
    partitionSelectionChanged = pyqtSignal(object)
    partitionsUpdated = pyqtSignal()

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._init_ui()
        self.refresh_partitions()

    def _init_ui(self):
        self.layout = QVBoxLayout(self) # Changed 'layout' to 'self.layout'
        self.layout.setContentsMargins(0, 0, 0, 0)  # 左右边距设为 0，让高亮条铺满
        
        self.tree = PartitionTreeWidget(self.db, self)
        self.tree.setObjectName("PartitionTree")
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setItemsExpandable(False)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.partitionsUpdated.connect(self.partitionsUpdated.emit)
        
        self.layout.addWidget(self.tree)
        # self.setLayout(self.layout) # QVBoxLayout(self) 已经自动设置了 layout

    def _on_item_double_clicked(self, item, column):
        if item.data(0, Qt.UserRole).get('type') == 'partition':
            item.setExpanded(not item.isExpanded())

    def _create_color_icon(self, color_str):
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(color_str or "#808080"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(2, 2, 12, 12, 4, 4)
        painter.end()
        return QIcon(pixmap)
        
    def _add_partition_recursive(self, partitions, parent_item, partition_counts):
        """递归函数，用于构建分区树UI"""
        for partition in partitions:
            count = partition_counts.get(partition.id, 0)
            item = QTreeWidgetItem(parent_item, [f"{partition.name} ({count})"])
            item.setData(0, Qt.UserRole, {'type': 'partition', 'id': partition.id, 'color': partition.color})
            item.setIcon(0, self._create_color_icon(partition.color))
            
            if partition.children:
                self._add_partition_recursive(partition.children, item, partition_counts)

    def refresh_partitions(self):
        """从数据库加载并递归显示分区"""
        current_selection = self.get_current_selection()
        self.tree.clear()
        
        counts = self.db.get_partition_item_counts()
        partition_counts = counts.get('partitions', {})

        # -- 添加静态项 --
        static_items = [
            ("全部数据", {'type': 'all', 'id': -1}, QStyle.SP_DirHomeIcon, counts.get('total', 0)),
            ("今日数据", {'type': 'today', 'id': -5}, QStyle.SP_FileDialogDetailedView, counts.get('today_modified', 0)),
            ("未分类", {'type': 'uncategorized', 'id': -2}, QStyle.SP_MessageBoxWarning, counts.get('uncategorized', 0)),
            ("未标签", {'type': 'untagged', 'id': -3}, QStyle.SP_DialogHelpButton, counts.get('untagged', 0)),
            ("回收站", {'type': 'trash', 'id': -4}, QStyle.SP_TrashIcon, counts.get('trash', 0)),
        ]
        
        for name, data, icon, count in static_items:
            item = QTreeWidgetItem(self.tree, [f"{name} ({count})"])
            item.setData(0, Qt.UserRole, data)
            item.setFont(0, QFont("Arial", 10, QFont.Bold))
            item.setIcon(0, self.style().standardIcon(icon))
            item.setFlags(item.flags() & ~Qt.ItemIsDragEnabled & ~Qt.ItemIsDropEnabled)

        # -- 递归添加用户分区 --
        top_level_partitions = self.db.get_partitions_tree()
        self._add_partition_recursive(top_level_partitions, self.tree, partition_counts)

        self.tree.expandAll()
        self.select_item_by_data(current_selection or {'type': 'all', 'id': -1})

    def select_item_by_data(self, data_to_find):
        if not data_to_find: return
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            item_data = item.data(0, Qt.UserRole)
            if item_data and item_data.get('id') == data_to_find.get('id') and item_data.get('type') == data_to_find.get('type'):
                self.tree.setCurrentItem(item)
                return
            it += 1

    def _on_selection_changed(self):
        if data := self.get_current_selection():
            self.partitionSelectionChanged.emit(None if data.get('type') == 'all' else data)

    def _show_context_menu(self, pos):
        menu = QMenu()
        item = self.tree.itemAt(pos)
        
        if item:
            item_data = item.data(0, Qt.UserRole)
            if item_data.get('type') == 'partition':
                menu.addAction("添加子分区", lambda: self._add_partition(item))
                menu.addAction("设置预设标签", lambda: self._set_partition_tags(item))
                menu.addAction("修改颜色", lambda: self._change_item_color(item))
                menu.addSeparator()
                menu.addAction("重命名", lambda: self._rename_item(item))
                menu.addAction("删除", lambda: self._delete_item(item))
            elif item_data.get('type') not in ['all', 'uncategorized', 'untagged', 'trash']:
                 menu.addAction("添加分区", self._add_partition) # fallback for safety
        else:
            menu.addAction("添加分区", self._add_partition)
            
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def _add_partition(self, parent_item=None):
        name, ok = QInputDialog.getText(self, "添加分区", "请输入分区名称:", QLineEdit.Normal, "")
        if ok and name:
            parent_id = parent_item.data(0, Qt.UserRole).get('id') if parent_item and parent_item.data(0, Qt.UserRole) else None
            if self.db.add_partition(name, parent_id=parent_id):
                self.partitionsUpdated.emit()

    def _change_item_color(self, item):
        item_data = item.data(0, Qt.UserRole)
        current_color = QColor(item_data.get('color', '#FFFFFF'))
        color = QColorDialog.getColor(current_color, self, "选择颜色")
        if color.isValid():
            self.db.update_partition(item_data['id'], color=color.name())
            self.partitionsUpdated.emit()

    def _rename_item(self, item):
        item_data = item.data(0, Qt.UserRole)
        old_name = item.text(0).split(' (')[0]
        new_name, ok = QInputDialog.getText(self, "重命名", "请输入新名称:", QLineEdit.Normal, old_name)
        if ok and new_name and new_name != old_name:
            self.db.rename_partition(item_data['id'], new_name)
            self.partitionsUpdated.emit()

    def _delete_item(self, item):
        item_data = item.data(0, Qt.UserRole)
        if item_data.get('type') != 'partition':
            log.warning(f"尝试删除一个非分区类型的项目: {item_data.get('type')}")
            return
        
        item_name = item.text(0).split(' (')[0]
        reply = QMessageBox.question(self, "确认删除", f"确定要删除分区 '{item_name}' 吗？\n此操作会将其本身及其所有子分区下的全部数据移至回收站。",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            if self.db.delete_partition(item_data['id']):
                self.partitionsUpdated.emit()
            else:
                QMessageBox.warning(self, "删除失败", f"无法删除分区 '{item_name}'。")
    
    def _set_partition_tags(self, item):
        item_data = item.data(0, Qt.UserRole)
        current_tags_str = ", ".join(self.db.get_partition_tags(item_data['id']))
        new_tags_str, ok = QInputDialog.getText(self, "设置预设标签", "请输入标签（用逗号分隔）:", QLineEdit.Normal, current_tags_str)
        if ok:
            tag_names = [tag.strip() for tag in new_tags_str.split(',') if tag.strip()]
            self.db.set_partition_tags(item_data['id'], tag_names)
            self.partitionsUpdated.emit()
            
    def get_current_selection(self):
        return self.tree.currentItem().data(0, Qt.UserRole) if self.tree.currentItem() else None
