# -*- coding: utf-8 -*-
"""
剪贴板管理器
使用策略模式处理不同类型的剪贴板数据
"""
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QMimeData

log = logging.getLogger("ClipboardSvc")


class ClipboardManager(QObject):
    """剪贴板管理器 - 使用策略模式"""
    
    data_captured = pyqtSignal(bool)

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.handlers = []
        self._register_handlers()
    
    def _register_handlers(self):
        """注册所有处理器，按优先级排序"""
        try:
            from handlers import ImageHandler, FileHandler, URLHandler, TextHandler
            
            # 创建处理器实例
            self.handlers = [
                ImageHandler(),   # 优先级 10 - 最高
                FileHandler(),    # 优先级 20
                URLHandler(),     # 优先级 30
                TextHandler(),    # 优先级 40 - 最低（兜底）
            ]
            
            # 按优先级排序（数字越小优先级越高）
            self.handlers.sort(key=lambda h: h.priority)
            
            log.info(f"✅ 注册了 {len(self.handlers)} 个处理器")
            for handler in self.handlers:
                log.debug(f"  - {handler.__class__.__name__} (优先级: {handler.priority})")
                
        except Exception as e:
            log.error(f"处理器注册失败: {e}", exc_info=True)
            self.handlers = []
    
    def process_clipboard(self, mime_data: QMimeData, partition_info: dict = None):
        """
        使用责任链模式处理剪贴板数据
        
        Args:
            mime_data: Qt剪贴板数据对象
            partition_info: (可选) 当前选中的分区信息
            
        Returns:
            bool: True表示成功处理，False表示未处理
        """
        try:
            # 遍历所有处理器
            for handler in self.handlers:
                if handler.can_handle(mime_data):
                    log.debug(f"使用 {handler.__class__.__name__} 处理")
                    item, is_new = handler.handle(mime_data, self.db, partition_info)
                    
                    if item and is_new:
                        # 成功创建了新项目
                        # 检查是否需要添加预设标签 (合并组和区的标签)
                        if partition_info and partition_info.get('type') == 'partition' and item.partition:
                            all_tags = set()
                            
                            # 获取区的标签
                            partition_tags = self.db.get_partition_tags(item.partition.id)
                            if partition_tags:
                                all_tags.update(partition_tags)
                            
                            # 获取组的标签
                            if item.partition.group_id:
                                group_tags = self.db.get_partition_group_tags(item.partition.group_id)
                                if group_tags:
                                    all_tags.update(group_tags)

                            if all_tags:
                                final_tags = list(all_tags)
                                log.info(f"为新项目 {item.id} 添加预设标签: {final_tags}")
                                self.db.add_tags_to_items([item.id], final_tags)

                        self.data_captured.emit(True)
                        return True
                    elif not is_new and item:
                        # 项目已存在
                        return False
            
            # 没有处理器能处理该数据
            formats = mime_data.formats()
            log.debug(f"没有合适的处理器。可用格式: {list(formats)}")
            return False
            
        except Exception as e:
            log.error(f"处理错误: {e}", exc_info=True)
            return False
