# -*- coding: utf-8 -*-
"""
文本处理器
处理纯文本剪贴板数据（排除URL）
"""
import logging
import re
from PyQt5.QtCore import QMimeData
from handlers.base_handler import BaseHandler

log = logging.getLogger("TextHandler")


class TextHandler(BaseHandler):
    """纯文本处理器"""
    
    def __init__(self):
        super().__init__(priority=40)  # 最低优先级，作为兜底
        self.url_pattern = re.compile(
            r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b'
            r'(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)'
        )
    
    def can_handle(self, mime_data: QMimeData) -> bool:
        """判断是否为纯文本（排除URL）"""
        if not mime_data.hasText():
            return False
        
        text = mime_data.text().strip()
        if not text:
            return False
        
        # 如果是URL，交给URL处理器
        if self.url_pattern.match(text):
            return False
        
        return True
    
    def handle(self, mime_data: QMimeData, db_manager, partition_info: dict = None):
        """处理纯文本"""
        try:
            text = mime_data.text().strip()
            
            # 去重检查
            if self._is_duplicate(text):
                log.debug("文本重复，跳过")
                return None, False
            
            partition_id = partition_info.get('id') if partition_info and partition_info.get('type') == 'partition' else None
            
            # 保存到数据库
            item, is_new = db_manager.add_item(
                text=text,
                item_type='text',
                is_file=False,
                partition_id=partition_id
            )
            
            if is_new:
                log.info(f"✅ 捕获文本: {text[:50]}...")
            
            return item, is_new
            
        except Exception as e:
            log.error(f"文本处理失败: {e}", exc_info=True)
            return None, False
