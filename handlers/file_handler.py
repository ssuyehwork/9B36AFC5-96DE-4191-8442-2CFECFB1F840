# -*- coding: utf-8 -*-
"""
文件处理器
处理文件路径剪贴板数据
"""
import logging
import os
from PyQt5.QtCore import QMimeData
from handlers.base_handler import BaseHandler

log = logging.getLogger("FileHandler")


class FileHandler(BaseHandler):
    """文件路径处理器"""
    
    def __init__(self):
        super().__init__(priority=20)  # 较高优先级
    
    def can_handle(self, mime_data: QMimeData) -> bool:
        """判断是否为文件路径"""
        if not mime_data.hasUrls():
            return False
        
        # 检查是否有本地文件
        local_files = [u.toLocalFile() for u in mime_data.urls() if u.isLocalFile()]
        return len(local_files) > 0
    
    def handle(self, mime_data: QMimeData, db_manager, partition_info: dict = None):
        """处理文件路径（目前只处理第一个）"""
        try:
            local_files = [u.toLocalFile() for u in mime_data.urls() if u.isLocalFile()]
            
            if not local_files:
                return None, False
            
            file_path = local_files[0] # 只处理第一个文件
            
            # 去重检查
            if self._is_duplicate(file_path):
                log.debug("文件路径重复，跳过")
                return None, False
            
            partition_id = partition_info.get('id') if partition_info and partition_info.get('type') == 'partition' else None
            
            item, is_new = db_manager.add_item(
                text=file_path,
                item_type='file',
                is_file=True,
                file_path=file_path,
                partition_id=partition_id
            )
            
            if is_new:
                log.info(f"✅ 捕获文件: {os.path.basename(file_path)}")

            return item, is_new
            
        except Exception as e:
            log.error(f"文件处理失败: {e}", exc_info=True)
            return None, False
