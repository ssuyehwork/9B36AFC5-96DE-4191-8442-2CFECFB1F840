# -*- coding: utf-8 -*-
import logging
from PyQt5.QtWidgets import QMenu, QMessageBox
from PyQt5.QtCore import QSettings
from ui.dialogs import ColorDialog
from core.shared import get_color_icon

log = logging.getLogger("ContextMenu")

class ContextMenuHandler:
    def __init__(self, main_window):
        self.mw = main_window
        self.db = main_window.db
        self.table = main_window.table
        log.info("✅ 右键菜单 Handler 就绪")

    def show_menu(self, pos):
        # 1. 坐标转换与有效性检查
        global_pos = self.table.mapToGlobal(pos)
        index = self.table.indexAt(pos)
        
        log.info(f"🖱️ 表格右键点击 - 局部坐标:{pos} -> 全局坐标:{global_pos}")
        
        if not index.isValid():
            log.warning("❌ 点击了空白区域，不显示菜单")
            return
        
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            log.warning("❌ 未选中任何行")
            return
            
        try:
            ids = [int(self.table.item(r.row(), 8).text()) for r in rows]  # ID列从9改为8
            log.info(f"✅ 选中 {len(ids)} 个条目，ID: {ids}")
        except Exception as e:
            log.error(f"❌ 解析ID失败: {e}", exc_info=True)
            return

        # 2. 根据上下文构建菜单
        try:
            menu = QMenu()
            
            partition_selection = self.mw.partition_panel.get_current_selection()
            
            if partition_selection and partition_selection.get('type') == 'trash':
                # 回收站菜单
                menu.addAction("♻️ 恢复").triggered.connect(lambda: self.restore_items(ids))
                menu.addSeparator()
                menu.addAction("💥 永久删除").triggered.connect(lambda: self.delete_permanently(ids))
            else:
                # 常规菜单
                # 星级
                sm = menu.addMenu("⭐ 设置星级")
                for i in range(6):
                    label = "★" * i if i > 0 else "无"
                    sm.addAction(label).triggered.connect(lambda _, l=i, x=ids: self.batch_set_star(x, l))
                
                menu.addSeparator()
                
                # 状态
                menu.addAction(f"❤️ 收藏/取消 ({len(ids)})").triggered.connect(lambda: self.batch_toggle(ids, 'is_favorite'))
                menu.addAction(f"📌 置顶/取消 ({len(ids)})").triggered.connect(lambda: self.batch_toggle(ids, 'is_pinned'))
                menu.addAction(f"🔒 锁定/解锁 ({len(ids)})").triggered.connect(lambda: self.batch_toggle(ids, 'is_locked'))
                
                menu.addSeparator()
                
                # 颜色
                cm = menu.addMenu("🎨 颜色标签")
                c1 = cm.addMenu("常用颜色")
                for n, c in [("紧急", "#f38ba8"), ("重要", "#f9e2af"), ("完成", "#a6e3a1")]:
                    c1.addAction(get_color_icon(c), n).triggered.connect(lambda _, cl=c, x=ids: self.batch_set_color(x, cl))
                
                hists = QSettings("ClipboardPro", "ColorHistory").value("colors", [])
                if hists:
                    c2 = cm.addMenu("历史记录")
                    for c in hists[:5]:
                        c2.addAction(get_color_icon(c), c).triggered.connect(lambda _, cl=c, x=ids: self.batch_set_color(x, cl))
                
                menu.addAction("选择新颜色...").triggered.connect(lambda: self.set_custom_color(ids))
                menu.addAction("清除颜色").triggered.connect(lambda: self.batch_set_color(ids, None))
                
                menu.addSeparator()
                menu.addAction("🗑️ 移至回收站").triggered.connect(lambda: self.move_to_trash(ids))

            log.info("🚀 菜单构建完成，正在弹出...")
            menu.exec_(global_pos)
            
        except Exception as e:
            log.critical(f"🔥 菜单显示崩溃: {e}", exc_info=True)

    # 业务逻辑
    def batch_set_star(self, ids, lvl):
        log.info(f"执行: 设置星级 {lvl}")
        for i in ids: self.db.update_item(i, star_level=lvl)
        self.mw.load_data()

    def batch_toggle(self, ids, field):
        log.info(f"执行: 切换状态 {field}")
        session = self.db.get_session()
        from data.database import ClipboardItem 
        first = session.query(ClipboardItem).get(ids[0])
        # 基于第一个元素取反，如果没有则默认True
        new_val = not getattr(first, field) if first else True
        session.close()
        
        # 批量更新
        for i in ids: self.db.update_item(i, **{field: new_val})
        self.mw.load_data()

    def batch_set_color(self, ids, color):
        log.info(f"执行: 设置颜色 {color}")
        for i in ids: self.db.update_item(i, custom_color=color)
        self.mw.load_data()
        
    def batch_group_smart(self, ids):
        """
        智能成组逻辑 (Ctrl+G):
        1. 检查选中项中所有不重复的颜色。
        2. 如果有多个颜色冲突 -> 弹出菜单让用户选择合并到哪个颜色 (或随机新色)。
        3. 如果只有一个颜色 -> 尝试合并到该颜色 (若全匹配则解组)。
        4. 如果都无颜色 -> 随机分配一个新颜色。
        """
        log.info("执行: 智能成组")
        session = self.db.get_session()
        from data.database import ClipboardItem
        items = session.query(ClipboardItem).filter(ClipboardItem.id.in_(ids)).all()
        
        # 收集所有非空颜色
        distinct_colors = set(item.custom_color for item in items if item.custom_color)
        
        apply_color = None
        
        # 莫兰迪色系
        palette = [
            "#ffadad", "#ffd6a5", "#fdffb6", "#caffbf", "#9bf6ff", "#a0c4ff", "#bdb2ff", "#ffc6ff",
            "#f72585", "#b5179e", "#7209b7", "#560bad", "#480ca8", "#3a0ca3", "#3f37c9", "#4361ee",
            "#4895ef", "#4cc9f0", "#f94144", "#f3722c", "#f8961e", "#f9844a", "#f9c74f", "#90be6d",
            "#43aa8b", "#4d908e", "#577590", "#277da1"
        ]
        
        if len(distinct_colors) > 1:
            # 场景C: 颜色冲突 -> 弹出选择菜单
            from PyQt5.QtGui import QCursor
            
            menu = QMenu()
            
            # 添加现有颜色选项
            for color in distinct_colors:
                action = menu.addAction(get_color_icon(color), f"合并到此颜色 {color.upper()}")
                action.setData(color)
            
            menu.addSeparator()
            
            # 添加随机新色选项
            import random
            rand_color = random.choice(palette)
            act_random = menu.addAction(get_color_icon(rand_color), "🎨 使用新随机颜色")
            act_random.setData(rand_color)
            
            # 弹出菜单
            selected = menu.exec_(QCursor.pos())
            if selected:
                apply_color = selected.data()
            else:
                # 用户取消
                session.close()
                return

        elif len(distinct_colors) == 1:
            # 场景A: 只有一个主色 -> 合并或解组
            target_color = list(distinct_colors)[0]
            all_match = all(item.custom_color == target_color for item in items)
            
            if all_match:
                # 全部已是该颜色 -> 取消 (Toggle Off)
                apply_color = None
                log.info(f"  ↪ 全部已是 {target_color} -> 取消分组")
            else:
                # 统一为该颜色
                apply_color = target_color
                log.info(f"  ↪ 合并分组至颜色 -> {target_color}")
        else:
            # 场景B: 全部无颜色 -> 新建随机分组
            import random
            apply_color = random.choice(palette)
            log.info(f"  ↪ 新建分组 -> {apply_color}")
            
        session.close()
        
        # 批量更新
        for i in ids: 
            self.db.update_item(i, custom_color=apply_color, group_color=apply_color)
        self.mw.load_data()

    def set_custom_color(self, ids):
        dlg = ColorDialog(self.mw)
        if dlg.exec_() and dlg.color:
            s = QSettings("ClipboardPro", "ColorHistory")
            h = s.value("colors", [], type=list)
            if dlg.color in h: h.remove(dlg.color)
            h.insert(0, dlg.color)
            s.setValue("colors", h[:10])
            self.batch_set_color(ids, dlg.color)

    def move_to_trash(self, ids):
        if QMessageBox.question(self.mw, "确认", f"移动 {len(ids)} 条记录到回收站?") == QMessageBox.Yes:
            log.info(f"执行: 移动 {len(ids)} 项到回收站")
            self.db.move_items_to_trash(ids)
            self.mw.load_data()
            self.mw.partition_panel.refresh_partitions()

    def restore_items(self, ids):
        log.info(f"执行: 从回收站恢复 {len(ids)} 项")
        self.db.restore_items_from_trash(ids)
        self.mw.load_data()
        self.mw.partition_panel.refresh_partitions()

    def delete_permanently(self, ids):
        if QMessageBox.question(self.mw, "警告", f"将永久删除 {len(ids)} 条记录，此操作不可恢复！\n确定要继续吗?", 
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            log.info(f"执行: 永久删除 {len(ids)} 项")
            self.db.delete_items_permanently(ids)
            self.mw.load_data()
            self.mw.partition_panel.refresh_partitions()