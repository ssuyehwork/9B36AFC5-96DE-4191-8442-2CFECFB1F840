# -*- coding: utf-8 -*-
"""
图片处理器
处理图片剪贴板数据（新功能）
"""
import logging
import os
import sys
import hashlib
from datetime import datetime
from PyQt5.QtCore import QMimeData, QBuffer, QByteArray, QIODevice
from PyQt5.QtGui import QImage
from handlers.base_handler import BaseHandler

log = logging.getLogger("ImageHandler")


class ImageHandler(BaseHandler):
    """图片处理器"""
    
    def __init__(self):
        super().__init__(priority=10)
    
    def can_handle(self, mime_data: QMimeData) -> bool:
        """判断是否为图片数据"""
        return mime_data.hasImage()
    
    def handle(self, mime_data: QMimeData, db_manager, partition_info: dict = None):
        """处理图片数据"""
        try:
            image = mime_data.imageData()
            if not image or image.isNull():
                log.warning("图片数据为空")
                return None, False
            
            qimage = QImage(image)
            if qimage.isNull():
                log.warning("无法解析图片")
                return None, False

            # 将 QImage 转换为二进制数据 (PNG格式)
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QIODevice.WriteOnly)
            qimage.save(buffer, "PNG")
            image_blob = byte_array.data()

            # 计算哈希用于去重
            img_hash = hashlib.md5(image_blob).hexdigest()
            if self._is_duplicate(img_hash):
                log.debug("图片重复，跳过")
                return None, False

            # 生成缩略图的二进制数据
            thumbnail_blob = self._create_thumbnail_blob(qimage)

            partition_id = partition_info.get('id') if partition_info and partition_info.get('type') == 'partition' else None
            
            item, is_new = db_manager.add_item(
                text=f"[图片] {qimage.width()}x{qimage.height()}",
                item_type='image',
                is_file=False,
                data_blob=image_blob,
                thumbnail_blob=thumbnail_blob,
                partition_id=partition_id
            )
            
            if is_new:
                size_kb = len(image_blob) / 1024
                log.info(f"✅ 捕获图片: {qimage.width()}x{qimage.height()} ({size_kb:.1f}KB)")

            return item, is_new
            
        except Exception as e:
            log.error(f"图片处理失败: {e}", exc_info=True)
            return None, False

    def _create_thumbnail_blob(self, qimage: QImage) -> bytes:
        """创建缩略图并返回其二进制数据"""
        try:
            thumb_size = 200
            thumbnail = qimage.scaled(thumb_size, thumb_size, aspectRatioMode=Qt.KeepAspectRatio, transformMode=Qt.SmoothTransformation)
            
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QIODevice.WriteOnly)
            thumbnail.save(buffer, "PNG")
            return byte_array.data()
        except Exception as e:
            log.error(f"创建缩略图失败: {e}")
            return None
