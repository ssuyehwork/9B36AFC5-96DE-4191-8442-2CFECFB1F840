# -*- coding: utf-8 -*-
"""
剪贴板处理器模块
导出所有处理器类
"""
from handlers.base_handler import BaseHandler
from handlers.text_handler import TextHandler
from handlers.file_handler import FileHandler
from handlers.image_handler import ImageHandler
from handlers.url_handler import URLHandler

__all__ = [
    'BaseHandler',
    'TextHandler',
    'FileHandler',
    'ImageHandler',
    'URLHandler'
]
