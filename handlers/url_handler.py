# -*- coding: utf-8 -*-
"""
URL处理器
处理URL链接剪贴板数据（新功能）
"""
import logging
import re
from urllib.parse import urlparse
from PyQt5.QtCore import QMimeData
from handlers.base_handler import BaseHandler

log = logging.getLogger("URLHandler")


class URLHandler(BaseHandler):
    """URL链接处理器"""
    
    def __init__(self):
        super().__init__(priority=30)  # 中等优先级
        # URL正则表达式
        self.url_pattern = re.compile(
            r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b'
            r'(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)'
        )
    
    def can_handle(self, mime_data: QMimeData) -> bool:
        """判断是否为URL"""
        if not mime_data.hasText():
            return False
        
        text = mime_data.text().strip()
        if not text:
            return False
        
        # 检查是否匹配URL格式
        return bool(self.url_pattern.match(text))
    
    def handle(self, mime_data: QMimeData, db_manager, partition_info: dict = None):
        """处理URL"""
        try:
            url = mime_data.text().strip()
            
            # 去重检查
            if self._is_duplicate(url):
                log.debug("URL重复，跳过")
                return None, False
            
            # 解析URL
            parsed = urlparse(url)
            domain = parsed.netloc or "未知域名"
            
            # 提取路径作为简短描述
            path = parsed.path.strip('/') or "首页"
            if len(path) > 30:
                path = path[:27] + "..."
            
            # 构建显示文本
            display_text = f"[链接] {domain}/{path}"
            
            partition_id = partition_info.get('id') if partition_info and partition_info.get('type') == 'partition' else None
            
            # 保存到数据库
            item, is_new = db_manager.add_item(
                text=url,
                item_type='url',
                is_file=False,
                url=url,
                url_domain=domain,
                url_title=path,  # 暂时使用路径作为标题
                partition_id=partition_id
            )
            
            if is_new:
                log.info(f"✅ 捕获URL: {domain}")
            
            return item, is_new
            
        except Exception as e:
            log.error(f"URL处理失败: {e}", exc_info=True)
            return None, False
