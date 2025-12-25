# -*- coding: utf-8 -*-
"""
剪贴板处理器基类
定义所有处理器的抽象接口
"""
from abc import ABC, abstractmethod
from PyQt5.QtCore import QMimeData
import logging

log = logging.getLogger("BaseHandler")


class BaseHandler(ABC):
    """剪贴板处理器抽象基类"""
    
    def __init__(self, priority=100):
        """
        初始化处理器
        
        Args:
            priority: 处理器优先级，数字越小优先级越高
        """
        self.priority = priority
        self.last_content = ""  # 用于去重
    
    @abstractmethod
    def can_handle(self, mime_data: QMimeData) -> bool:
        """
        判断是否能处理该剪贴板数据
        
        Args:
            mime_data: Qt剪贴板数据对象
            
        Returns:
            bool: True表示可以处理，False表示不能处理
        """
        pass
    
    @abstractmethod
    def handle(self, mime_data: QMimeData, db_manager, partition_info: dict = None):
        """
        处理剪贴板数据
        
        Args:
            mime_data: Qt剪贴板数据对象
            db_manager: 数据库管理器实例
            partition_info: (可选) 分区信息 {'type': 'group'/'partition', 'id': ID}
            
        Returns:
            Tuple[Optional[ClipboardItem], bool]: (新项目, 是否为新)
        """
        pass
    
    def _is_duplicate(self, content: str) -> bool:
        """
        检查内容是否重复
        
        Args:
            content: 要检查的内容
            
        Returns:
            bool: True表示重复，False表示不重复
        """
        if content == self.last_content:
            return True
        self.last_content = content
        return False
