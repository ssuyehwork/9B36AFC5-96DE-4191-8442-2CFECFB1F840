def toolbar_set_color(self):
    """从标题栏颜色按钮设置选中项的颜色"""
    rows = self.table.selectionModel().selectedRows()
    if not rows:
        QMessageBox.information(self, "提示", "请先选择要设置颜色的项目")
        return
    
    item_ids = [int(self.table.item(r.row(), 9).text()) for r in rows]
    self.set_custom_color(item_ids)

def set_custom_color(self, item_ids):
    """打开颜色选择对话框"""
    from PyQt5.QtWidgets import QColorDialog
    color = QColorDialog.getColor()
    if color.isValid():
        self.batch_set_color(item_ids, color.name())

def batch_set_color(self, ids, clr):
    """批量设置颜色"""
    session = self.db.get_session()
    try:
        from data.database import ClipboardItem
        for item_id in ids:
            if item := session.query(ClipboardItem).get(item_id):
                item.custom_color = clr
        session.commit()
        self.load_data()
    except Exception as e:
        log.error(f"设置颜色失败: {e}")
        session.rollback()
    finally:
        session.close()
