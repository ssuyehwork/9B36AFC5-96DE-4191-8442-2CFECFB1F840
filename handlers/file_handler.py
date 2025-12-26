# -*- coding: utf-8 -*-
"""
文件处理器
处理文件剪贴板数据，将单个或多个文件打包存入数据库
"""
import logging
import os
import io
import zipfile
from PyQt5.QtCore import QMimeData
from handlers.base_handler import BaseHandler

log = logging.getLogger("FileHandler")


class FileHandler(BaseHandler):
    """文件处理器 (支持多文件打包)"""
    
    def __init__(self):
        super().__init__(priority=20)
    
    def can_handle(self, mime_data: QMimeData) -> bool:
        """判断剪贴板中是否有本地文件"""
        if not mime_data.hasUrls():
            return False
        
        # 检查并确认至少有一个URL是本地文件
        for url in mime_data.urls():
            if url.isLocalFile():
                return True
        return False
    
    def handle(self, mime_data: QMimeData, db_manager, partition_info: dict = None):
        """处理文件，将单个文件或多个文件的ZIP包存入数据库"""
        try:
            local_files = [u.toLocalFile() for u in mime_data.urls() if u.isLocalFile()]
            
            if not local_files:
                return None, False
            
            # --- 生成UI显示文本 ---
            filenames = [os.path.basename(p) for p in local_files]
            if len(local_files) == 1:
                display_text = f"文件: {filenames[0]}"
            else:
                display_text = f"压缩包 ({len(filenames)}个文件): {', '.join(filenames)}"
            
            # 智能截断，避免过长
            if len(display_text) > 150:
                 display_text = f"压缩包 ({len(filenames)}个文件): {filenames[0]}, {filenames[1]}..."

            # --- 去重检查 (基于生成的显示文本) ---
            if self._is_duplicate(display_text):
                log.debug("文件组合重复，跳过")
                return None, False
            
            # --- 处理文件数据 ---
            file_blob = None
            if len(local_files) == 1:
                # 单个文件: 直接读取二进制内容
                log.info(f"读取单个文件: {local_files[0]}")
                with open(local_files[0], 'rb') as f:
                    file_blob = f.read()
            else:
                # 多个文件: 在内存中创建ZIP压缩包
                log.info(f"打包 {len(local_files)} 个文件到内存ZIP...")
                mem_zip = io.BytesIO()
                with zipfile.ZipFile(mem_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
                    for file_path in local_files:
                        zf.write(file_path, arcname=os.path.basename(file_path))
                mem_zip.seek(0)
                file_blob = mem_zip.read()
            
            if not file_blob:
                log.warning("未能成功生成文件或压缩包的二进制数据")
                return None, False

            # --- 存入数据库 ---
            partition_id = partition_info.get('id') if partition_info and partition_info.get('type') == 'partition' else None
            
            item, is_new = db_manager.add_item(
                text=display_text,
                item_type='file',
                is_file=True,
                file_path=';'.join(local_files),  # 存储原始路径列表，用分号分隔
                data_blob=file_blob,              # 存储实际的文件二进制数据或ZIP数据
                partition_id=partition_id
            )
            
            if is_new:
                log.info(f"✅ 成功捕获 {len(local_files)} 个文件到数据库")

            return item, is_new
            
        except Exception as e:
            log.error(f"处理文件剪贴板数据失败: {e}", exc_info=True)
            return None, False
