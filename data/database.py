# -*- coding: utf-8 -*-
import sys
import os
import hashlib
import logging
from datetime import datetime, timedelta, time
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Table, Index, Float, func, or_, exists, and_, BLOB
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, joinedload, subqueryload

log = logging.getLogger("Database")
Base = declarative_base()

item_tags = Table(
    'item_tags', Base.metadata,
    Column('item_id', Integer, ForeignKey('clipboard_items.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True),
    Index('idx_tag_item', 'tag_id', 'item_id')
)

partition_tags = Table(
    'partition_tags', Base.metadata,
    Column('partition_id', Integer, ForeignKey('partitions.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

class Partition(Base):
    __tablename__ = 'partitions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    color = Column(String(20), default=None)
    sort_index = Column(Float, default=0.0)
    
    # 新增 parent_id 以支持层级结构
    parent_id = Column(Integer, ForeignKey('partitions.id'), nullable=True)
    
    # 建立父子关系
    parent = relationship("Partition", remote_side=[id], back_populates="children")
    children = relationship("Partition", back_populates="parent", cascade="all, delete-orphan", order_by="Partition.sort_index")
    
    tags = relationship("Tag", secondary=partition_tags, back_populates="partitions")
    items = relationship(
        "ClipboardItem", 
        primaryjoin="and_(Partition.id==ClipboardItem.partition_id, ClipboardItem.is_deleted != True)",
        back_populates="partition", 
        order_by="ClipboardItem.sort_index"
    )

class ClipboardItem(Base):
    __tablename__ = 'clipboard_items'
    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), index=True, unique=True)
    note = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now)
    modified_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_visited_at = Column(DateTime, default=datetime.now)
    visit_count = Column(Integer, default=0)
    sort_index = Column(Float, default=0.0)
    star_level = Column(Integer, default=0) 
    is_favorite = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)
    is_pinned = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False, index=True) # 回收站功能
    group_color = Column(String(20), default=None)
    custom_color = Column(String(20), default=None)
    is_file = Column(Boolean, default=False)
    file_path = Column(Text, default=None)
    
    # 新增字段：支持图片和URL
    item_type = Column(String(20), default='text')  # 'text', 'file', 'image', 'url'
    image_path = Column(Text, default=None)         # 图片本地路径（保留，用于兼容旧数据）
    thumbnail_path = Column(Text, default=None)     # 缩略图路径（保留，用于兼容旧数据）
    url = Column(Text, default=None)                # URL地址
    url_title = Column(String(200), default=None)   # URL标题
    url_domain = Column(String(100), default=None)  # URL域名
    
    # 新增二进制数据存储
    data_blob = Column(BLOB, nullable=True)         # 储存图片、富文本等二进制数据
    thumbnail_blob = Column(BLOB, nullable=True)    # 储存缩略图的二进制数据
    
    partition_id = Column(Integer, ForeignKey('partitions.id'), nullable=True)
    original_partition_id = Column(Integer, nullable=True) # 用于恢复功能
    partition = relationship("Partition", back_populates="items")
    tags = relationship("Tag", secondary=item_tags, back_populates="items")

class Tag(Base):
    __tablename__ = 'tags'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    items = relationship("ClipboardItem", secondary=item_tags, back_populates="tags")
    partitions = relationship("Partition", secondary=partition_tags, back_populates="tags")

class DBManager:
    def __init__(self, db_name='clipboard_data.db'):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        
        db_path = os.path.join(base_dir, db_name)
        log.info(f"数据库路径: {db_path}")

        try:
            self.engine = create_engine(f'sqlite:///{db_path}?check_same_thread=False', echo=False)
            # 先创建所有表（如果不存在）
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
            # 然后执行迁移（添加新字段）
            # 注意：这里不检查文件是否存在，因为create_all已经创建了
            self._check_migrations()
        except Exception as e:
            log.critical(f"数据库初始化失败: {e}", exc_info=True)

    def _check_migrations(self):
        """检查并为所有模型执行数据库迁移，包括从旧的分组/分区模型进行数据迁移。"""
        from sqlalchemy import inspect, text
        try:
            log.info("通用迁移检查：使用 SQLAlchemy Inspector")
            inspector = inspect(self.engine)
            
            with self.engine.connect() as connection:
                # 步骤 1: 确保所有模型的所有新列都已添加
                add_col_transaction = connection.begin()
                try:
                    for table_name, table in Base.metadata.tables.items():
                        log.debug(f"检查表 '{table_name}' 的迁移...")
                        existing_cols = {c['name'] for c in inspector.get_columns(table_name)}
                        for column in table.columns:
                            if column.name not in existing_cols:
                                col_type = column.type.compile(self.engine.dialect)
                                stmt = text(f'ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}')
                                connection.execute(stmt)
                                log.info(f"✅ 表 '{table_name}' 中添加字段: {column.name}")
                    add_col_transaction.commit()
                except Exception as e:
                    log.error(f"添加新列失败，正在回滚: {e}")
                    add_col_transaction.rollback()
                    raise

                # 步骤 2: 检查是否需要从旧的 partition_groups 模型进行数据迁移
                if inspector.has_table("partition_groups"):
                    log.info("检测到旧的 partition_groups 表，开始数据迁移...")
                    migration_transaction = connection.begin()
                    try:
                        # 1. 获取所有组及其标签
                        groups = connection.execute(text("SELECT id, name, color, sort_index FROM partition_groups ORDER BY id")).fetchall()
                        group_tags_results = connection.execute(text("SELECT partition_group_id, tag_id FROM partition_group_tags")).fetchall()
                        group_tags_map = {}
                        for group_id, tag_id in group_tags_results:
                            group_tags_map.setdefault(group_id, []).append(tag_id)

                        # 2. 迁移每个组
                        for old_group_id, name, color, sort_index in groups:
                            # 将组作为新的顶层分区插入
                            result = connection.execute(text(
                                "INSERT INTO partitions (name, color, sort_index, parent_id) VALUES (:name, :color, :sort_index, NULL)"
                            ), {"name": name, "color": color, "sort_index": sort_index})
                            
                            new_parent_id = result.lastrowid
                            log.info(f"  - 分组 '{name}' (ID:{old_group_id}) 已迁移为顶层分区 (ID:{new_parent_id})")

                            # 更新其原来的子分区，将 group_id 替换为新的 parent_id
                            # 注意：我们假设旧的 partitions 表有一个 group_id 列
                            update_stmt = text("UPDATE partitions SET parent_id = :parent_id WHERE group_id = :group_id")
                            connection.execute(update_stmt, {"parent_id": new_parent_id, "group_id": old_group_id})

                            # 迁移标签
                            if old_group_id in group_tags_map:
                                for tag_id in group_tags_map[old_group_id]:
                                    connection.execute(text(
                                        "INSERT INTO partition_tags (partition_id, tag_id) VALUES (:p_id, :t_id)"
                                    ), {"p_id": new_parent_id, "t_id": tag_id})
                                log.info(f"    - 成功迁移 {len(group_tags_map[old_group_id])} 个标签")

                        # 3. 删除旧的表
                        connection.execute(text("DROP TABLE partition_group_tags"))
                        connection.execute(text("DROP TABLE partition_groups"))
                        log.info("旧的 partition_group_tags 和 partition_groups 表已成功删除。")
                        
                        log.warning("旧的 partitions.group_id 列已保留在数据库中，但不会被使用。")

                        migration_transaction.commit()
                        log.info("✅ 分区数据迁移成功完成！")
                    except Exception as e:
                        log.error(f"分区数据迁移失败，正在回滚: {e}")
                        migration_transaction.rollback()
                        raise
        except Exception as e:
            log.error(f"迁移检查失败: {e}", exc_info=True)

    def get_session(self): return self.Session()

    def add_item(self, text, is_file=False, file_path=None, item_type='text', 
                 image_path=None, thumbnail_path=None, url=None, url_title=None, 
                 url_domain=None, partition_id=None, data_blob=None, thumbnail_blob=None):
        """
        添加剪贴板项
        
        Args:
            text: 内容文本
            is_file: 是否为文件
            file_path: 文件路径
            item_type: 项目类型 ('text', 'file', 'image', 'url')
            image_path: 图片路径
            thumbnail_path: 缩略图路径
            url: URL地址
            url_title: URL标题
            url_domain: URL域名
            partition_id: (可选) 关联的分区ID
            data_blob: (可选) 二进制数据
            thumbnail_blob: (可选) 缩略图二进制数据
        """
        session = self.get_session()
        try:
            text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
            existing = session.query(ClipboardItem).filter_by(content_hash=text_hash).first()
            if existing:
                existing.last_visited_at = datetime.now()
                existing.modified_at = datetime.now()
                existing.visit_count += 1
                if partition_id and not existing.partition_id:
                     existing.partition_id = partition_id
                session.commit()
                return existing, False
            
            min_sort = session.query(func.min(ClipboardItem.sort_index)).scalar()
            new_sort = (min_sort - 1.0) if min_sort is not None else 0.0
            note_txt = os.path.basename(file_path) if is_file and file_path else text.split('\n')[0][:50]
            
            new_item = ClipboardItem(
                content=text,
                content_hash=text_hash,
                sort_index=new_sort,
                note=note_txt,
                is_file=is_file,
                file_path=file_path,
                item_type=item_type,
                image_path=image_path,
                thumbnail_path=thumbnail_path,
                url=url,
                url_title=url_title,
                url_domain=url_domain,
                partition_id=partition_id,
                data_blob=data_blob,
                thumbnail_blob=thumbnail_blob
            )
            session.add(new_item)
            try:
                session.commit()
                session.refresh(new_item)
                return new_item, True
            except Exception as e:
                # 捕获可能的并发写入冲突 (Unique Constraint)
                session.rollback()
                log.warning(f"写入冲突，尝试作为更新理: {e}")
                existing = session.query(ClipboardItem).filter_by(content_hash=text_hash).first()
                if existing:
                    existing.last_visited_at = datetime.now()
                    existing.visit_count += 1
                    session.commit()
                    return existing, False
                else:
                    # 如果还是查不到，那可能是其他错误，抛出
                    log.error(f"严重写入失败: {e}")
                    return None, False
        except Exception as e:
            log.error(f"写入失败: {e}")
            session.rollback()
            return None, False
        finally:
            session.close()

    def _build_query(self, session, filters=None, search="", selected_tags=None, sort_mode="manual", date_filter=None, date_modify_filter=None, partition_filter=None, include_deleted=False):
        log.debug(f"🔍 构建查询: filters={filters}, search='{search}', tags={selected_tags}, sort={sort_mode}, date={date_filter}, date_modify={date_modify_filter}, partition={partition_filter}, deleted={include_deleted}")
        q = session.query(ClipboardItem).options(joinedload(ClipboardItem.tags))

        # 核心回收站逻辑
        if include_deleted:
            q = q.filter(ClipboardItem.is_deleted == True)
        else:
            # 使用 != True 来同时处理 False 和 NULL (旧数据) 的情况
            q = q.filter(ClipboardItem.is_deleted != True)
        
        # 分区筛选
        if partition_filter:
            ptype = partition_filter.get('type')
            pid = partition_filter.get('id')
            if ptype == 'partition':
                # 新逻辑：筛选出该分区及其所有子孙分区的项目
                all_partition_ids = self._get_all_descendant_ids(session, pid)
                q = q.filter(ClipboardItem.partition_id.in_(all_partition_ids))
            elif ptype == 'uncategorized':
                q = q.filter(ClipboardItem.partition_id == None)
            elif ptype == 'untagged':
                q = q.filter(~exists().where(item_tags.c.item_id == ClipboardItem.id))

        if filters:
            if filters.get('stars'): 
                log.debug(f"⭐ 应用星级筛选: {filters['stars']}")
                q = q.filter(ClipboardItem.star_level.in_(filters['stars']))
            if filters.get('colors'):
                log.debug(f"🎨 应用颜色筛选: {filters['colors']}")
                q = q.filter(ClipboardItem.custom_color.in_(filters['colors']))
            if filters.get('types'):
                log.debug(f"📄 应用类型筛选: {filters['types']}")
                
                type_conditions = []
                # 分离标准类型和扩展名
                standard_types = ['text', 'url']
                selected_standard = [t for t in filters['types'] if t in standard_types]
                selected_extensions = [t for t in filters['types'] if t not in standard_types and t != 'folder']
                selected_folder = 'folder' in filters['types']
                
                if selected_standard:
                    type_conditions.append(ClipboardItem.item_type.in_(selected_standard))
                
                if selected_folder:
                     type_conditions.append(ClipboardItem.item_type == 'file')
                
                if selected_extensions:
                    ext_conditions = []
                    for ext in selected_extensions:
                        pattern = f"%.{ext}"
                        ext_conditions.append(ClipboardItem.file_path.like(pattern))
                        ext_conditions.append(ClipboardItem.image_path.like(pattern))
                    type_conditions.append(or_(*ext_conditions))
                
                if type_conditions:
                    q = q.filter(or_(*type_conditions))
        
        if selected_tags: 
            log.debug(f"🏷️ 应用标签筛选: {selected_tags}")
            q = q.join(item_tags).join(Tag).filter(Tag.name.in_(selected_tags))
        
        if search:
            log.debug(f"🔎 应用搜索: '{search}'")
            search_pattern = f"%{search}%"
            # 优化：使用子查询来分别查找匹配的ID，然后用OR组合，避免复杂的JOIN和DISTINCT
            content_search_sq = session.query(ClipboardItem.id).filter(or_(ClipboardItem.content.like(search_pattern), ClipboardItem.note.like(search_pattern))).subquery()
            tag_search_sq = session.query(item_tags.c.item_id).join(Tag).filter(Tag.name.like(search_pattern)).subquery()
            q = q.filter(or_(ClipboardItem.id.in_(content_search_sq), ClipboardItem.id.in_(tag_search_sq)))
        
        # 创建日期筛选逻辑
        if date_filter:
            now = datetime.now()
            today = now.date()
            start_dt, end_dt = None, None
            
            if date_filter == "今日":
                start_dt = datetime.combine(today, time.min)
                end_dt = datetime.combine(today, time.max)
            elif date_filter == "昨日":
                start_dt = datetime.combine(today - timedelta(days=1), time.min)
                end_dt = datetime.combine(today - timedelta(days=1), time.max)
            elif date_filter == "周内":
                start_dt = datetime.combine(today - timedelta(days=7), time.min)
            elif date_filter == "两周":
                start_dt = datetime.combine(today - timedelta(days=14), time.min)
            elif date_filter == "本月":
                start_dt = datetime.combine(today.replace(day=1), time.min)
            elif date_filter == "上月":
                first_day = today.replace(day=1)
                last_month_last_day = first_day - timedelta(days=1)
                last_month_first_day = last_month_last_day.replace(day=1)
                start_dt = datetime.combine(last_month_first_day, time.min)
                end_dt = datetime.combine(last_month_last_day, time.max)
            
            if start_dt: q = q.filter(ClipboardItem.created_at >= start_dt)
            if end_dt: q = q.filter(ClipboardItem.created_at <= end_dt)
        
        # 修改日期筛选逻辑
        if date_modify_filter:
            now = datetime.now()
            today = now.date()
            start_dt, end_dt = None, None
            
            if date_modify_filter == "今日":
                start_dt = datetime.combine(today, time.min)
                end_dt = datetime.combine(today, time.max)
            elif date_modify_filter == "昨日":
                start_dt = datetime.combine(today - timedelta(days=1), time.min)
                end_dt = datetime.combine(today - timedelta(days=1), time.max)
            elif date_modify_filter == "周内":
                start_dt = datetime.combine(today - timedelta(days=7), time.min)
            elif date_modify_filter == "两周":
                start_dt = datetime.combine(today - timedelta(days=14), time.min)
            elif date_modify_filter == "本月":
                start_dt = datetime.combine(today.replace(day=1), time.min)
            elif date_modify_filter == "上月":
                first_day = today.replace(day=1)
                last_month_last_day = first_day - timedelta(days=1)
                last_month_first_day = last_month_last_day.replace(day=1)
                start_dt = datetime.combine(last_month_first_day, time.min)
                end_dt = datetime.combine(last_month_last_day, time.max)
            
            if start_dt: q = q.filter(ClipboardItem.modified_at >= start_dt)
            if end_dt: q = q.filter(ClipboardItem.modified_at <= end_dt)
            
        if sort_mode == "manual": q = q.order_by(ClipboardItem.is_pinned.desc(), ClipboardItem.sort_index.asc())
        elif sort_mode == "time": q = q.order_by(ClipboardItem.is_pinned.desc(), ClipboardItem.created_at.desc())
        elif sort_mode == "size": q = q.order_by(ClipboardItem.is_pinned.desc(), func.length(ClipboardItem.content).desc())
        elif sort_mode == "stars": q = q.order_by(ClipboardItem.is_pinned.desc(), ClipboardItem.star_level.desc())
        elif sort_mode == "visit": q = q.order_by(ClipboardItem.is_pinned.desc(), ClipboardItem.visit_count.desc())
        return q

    def get_items(self, filters=None, search="", sort_mode="manual", selected_tags=None, 
                  limit=50, offset=0, date_filter=None, date_modify_filter=None, partition_filter=None):
        """
        获取剪贴板项列表
        filters, search, selected_tags 用于前端过滤，这里不再使用
        """
        with self.Session() as session:
            try:
                include_deleted = (partition_filter and partition_filter.get('type') == 'trash')
                
                # === 修改：不传入 filters, search, selected_tags ===
                q = self._build_query(
                    session, 
                    filters=None,  # 前端筛选
                    search="",     # 前端搜索
                    selected_tags=None,  # 前端标签
                    sort_mode=sort_mode, 
                    date_filter=date_filter, 
                    date_modify_filter=date_modify_filter, 
                    partition_filter=partition_filter, 
                    include_deleted=include_deleted
                )
                
                total_found = q.count()
                log.info(f"数据库查询：匹配到 {total_found} 条结果。")
                
                results = q.limit(limit).offset(offset).all()
                log.info(f"数据库查询：应用分页后，返回 {len(results)} 条数据。")
                
                return results
            except Exception as e:
                log.error(f"查询失败: {e}", exc_info=True)
                return []


    def get_count(self, filters=None, search="", selected_tags=None, date_filter=None, 
                  date_modify_filter=None, partition_filter=None):
        """获取符合条件的项目总数（不包含前端筛选）"""
        with self.Session() as session:
            try:
                include_deleted = (partition_filter and partition_filter.get('type') == 'trash')
                
                # === 修改：不传入 filters, search, selected_tags ===
                q = self._build_query(
                    session, 
                    filters=None, 
                    search="", 
                    selected_tags=None, 
                    sort_mode="manual", 
                    date_filter=date_filter, 
                    date_modify_filter=date_modify_filter, 
                    partition_filter=partition_filter, 
                    include_deleted=include_deleted
                )
                count = q.count()
                log.info(f"数据库计数：总数 {count} 条。")
                return count
            except Exception as e:
                log.error(f"计数失败: {e}", exc_info=True)
                return 0

    def update_item(self, item_id, **kwargs):
        """更新剪贴板项属性"""
        with self.Session() as session:
            try:
                item = session.query(ClipboardItem).get(item_id)
                if item:
                    for k, v in kwargs.items():
                        setattr(item, k, v)
                    session.commit()
                    return True
                return False
            except Exception as e:
                log.error(f"更新失败: {e}")
                session.rollback()
                return False

    def move_items_to_trash(self, ids):
        """将多个项目移动到回收站（逻辑删除），并记录原始分区ID。"""
        with self.Session() as session:
            try:
                items_to_trash = session.query(ClipboardItem).filter(
                    ClipboardItem.id.in_(ids),
                    ClipboardItem.is_locked == False
                ).all()

                for item in items_to_trash:
                    item.original_partition_id = item.partition_id
                    item.partition_id = None
                    item.is_deleted = True
                
                session.commit()
            except Exception as e:
                log.error(f"移动到回收站失败: {e}")
                session.rollback()

    def restore_items_from_trash(self, ids):
        """从回收站智能恢复项目。"""
        with self.Session() as session:
            try:
                # 1. 获取所有要恢复的项目
                items_to_restore = session.query(ClipboardItem).filter(ClipboardItem.id.in_(ids)).all()
                if not items_to_restore:
                    return

                # 2. 一次性获取所有现存的分区ID，以提高效率
                existing_partition_ids = {p_id for p_id, in session.query(Partition.id).all()}

                for item in items_to_restore:
                    item.is_deleted = False
                    
                    # 检查原始分区是否存在
                    if item.original_partition_id and item.original_partition_id in existing_partition_ids:
                        # 如果存在，恢复到原始分区
                        item.partition_id = item.original_partition_id
                    else:
                        # 否则，恢复到“未分类”
                        item.partition_id = None
                    
                    # 清空临时记录
                    item.original_partition_id = None
                
                session.commit()
            except Exception as e:
                log.error(f"从回收站恢复失败: {e}")
                session.rollback()

    def delete_items_permanently(self, ids):
        """永久删除项目"""
        with self.Session() as session:
            try:
                session.query(ClipboardItem).filter(
                    ClipboardItem.id.in_(ids)
                ).delete(synchronize_session=False)
                session.commit()
            except Exception as e:
                log.error(f"永久删除失败: {e}")
                session.rollback()

    def update_sort_order(self, ids):
        """更新项目排序顺序"""
        with self.Session() as session:
            try:
                for idx, i in enumerate(ids):
                    if item := session.query(ClipboardItem).get(i):
                        item.sort_index = float(idx)
                session.commit()
            except Exception as e:
                log.error(f"更新排序失败: {e}")
                session.rollback()

    def get_stats(self):
        """获取统计信息"""
        stats = {'tags': [], 'stars': {}, 'colors': {}, 'types': {}}
        with self.Session() as session:
            try:
                # 修复：使用 outerjoin 确保所有标签都被统计，即使它们没有关联任何项目
                stats['tags'] = session.query(Tag.name, func.count(item_tags.c.item_id)).outerjoin(item_tags).group_by(Tag.id).all()
                
                # 修复: 恢复 stars 查询
                stars = session.query(ClipboardItem.star_level, func.count(ClipboardItem.id)).group_by(ClipboardItem.star_level).all()
                stats['stars'] = {s: c for s, c in stars}
                
                colors = session.query(ClipboardItem.custom_color, func.count(ClipboardItem.id)).group_by(ClipboardItem.custom_color).all()
                stats['colors'] = {c: count for c, count in colors if c}
                
                # === 重构：类型统计 (支持文件夹和扩展名) ===
                # 获取所有项目的类型和路径信息，在内存中统一处理
                # 这样可以确保 图片 类型也能按扩展名归类
                all_items = session.query(
                    ClipboardItem.item_type, 
                    ClipboardItem.file_path, 
                    ClipboardItem.image_path
                ).all()
                
                type_counts = {}
                
                for item_type, file_path, image_path in all_items:
                    key = item_type # 默认使用类型 (text, url)
                    
                    if item_type == 'file' and file_path:
                        if os.path.exists(file_path):
                            if os.path.isdir(file_path):
                                key = 'folder'
                            else:
                                _, ext = os.path.splitext(file_path)
                                key = ext.lstrip('.').upper() if ext else 'FILE'
                    
                    elif item_type == 'image':
                        # 图片类型尝试获取扩展名
                        path = image_path or file_path
                        if path:
                            _, ext = os.path.splitext(path)
                            key = ext.lstrip('.').upper() if ext else 'IMAGE'
                        else:
                            key = 'IMAGE'
                            
                    # 统一转大写用于显示
                    if key not in ['text', 'url', 'folder']:
                        key = key.upper()
                        
                    type_counts[key] = type_counts.get(key, 0) + 1
                
                stats['types'] = type_counts
                
                # === 新增：日期统计 ===
                stats['date_create'] = self._get_date_counts(session, ClipboardItem.created_at)
                stats['date_modify'] = self._get_date_counts(session, ClipboardItem.modified_at)
                
                return stats
            except Exception as e:
                log.error(f"获取统计失败: {e}", exc_info=True)
                return stats

    def _get_date_counts(self, session, date_column):
        """统计各个时间段的数量"""
        now = datetime.now()
        today = now.date()
        
        # 定义时间段 (与 panel_filter 对应)
        ranges = {
            "今日": (datetime.combine(today, time.min), datetime.combine(today, time.max)),
            "昨日": (datetime.combine(today - timedelta(days=1), time.min), datetime.combine(today - timedelta(days=1), time.max)),
            "周内": (datetime.combine(today - timedelta(days=7), time.min), None),
            "两周": (datetime.combine(today - timedelta(days=14), time.min), None),
            "本月": (datetime.combine(today.replace(day=1), time.min), None)
        }
        
        # 上月单独逻辑
        first_day = today.replace(day=1)
        last_month_last_day = first_day - timedelta(days=1)
        last_month_first_day = last_month_last_day.replace(day=1)
        ranges["上月"] = (datetime.combine(last_month_first_day, time.min), datetime.combine(last_month_last_day, time.max))
        
        counts = {}
        for label, (start, end) in ranges.items():
            q = session.query(func.count(ClipboardItem.id)).filter(date_column >= start)
            if end:
                q = q.filter(date_column <= end)
            counts[label] = q.scalar()
            
        return counts

    
    def add_tags_to_items(self, item_ids, tag_names):
        """为多个项目批量添加多个标签"""
        with self.Session() as session:
            try:
                items = session.query(ClipboardItem).filter(ClipboardItem.id.in_(item_ids)).all()
                if not items:
                    return

                for name in tag_names:
                    name = name.strip()
                    if not name:
                        continue
                    
                    # 查找或创建标签
                    tag = session.query(Tag).filter_by(name=name).first()
                    if not tag:
                        tag = Tag(name=name)
                        session.add(tag)
                        # 立即刷新以获取 tag.id (如果需要)
                        session.flush()

                    # 为每个项目关联标签
                    for item in items:
                        if tag not in item.tags:
                            item.tags.append(tag)
                
                session.commit()
            except Exception as e:
                log.error(f"批量添加标签失败: {e}")
                session.rollback()

    def remove_tag_from_item(self, item_id, tag_name):
        """从项目移除标签"""
        with self.Session() as session:
            try:
                item = session.query(ClipboardItem).get(item_id)
                tag = session.query(Tag).filter_by(name=tag_name).first()
                if item and tag and tag in item.tags:
                    item.tags.remove(tag)
                    session.commit()
            except Exception as e:
                log.error(f"移除标签失败: {e}")
                session.rollback()

    def auto_delete_old_data(self, days=21):
        """自动删除旧数据（不删除锁定的）"""
        with self.Session() as session:
            try:
                cutoff = datetime.now() - timedelta(days=days)
                count = session.query(ClipboardItem).filter(
                    ClipboardItem.created_at < cutoff,
                    ClipboardItem.is_locked == False
                ).delete(synchronize_session=False)
                session.commit()
                return count
            except Exception as e:
                log.error(f"清理旧数据失败: {e}")
                session.rollback()
                return 0

    # ==============================================================================
    # 分区和组管理
    # ==============================================================================

    def get_partitions_tree(self):
        """
        获取所有分区并以树状结构返回顶层分区。
        该方法在会话中完全加载整个树，以避免在UI层发生DetachedInstanceError。
        """
        with self.Session() as session:
            try:
                # 1. 一次性加载所有分区到会话中
                all_partitions = session.query(Partition).order_by(Partition.sort_index).all()
                
                # 2. 强制加载 children 关系
                # 通过访问每个分区的 children 属性，SQLAlchemy 的懒加载机制会从
                # session 中已有的对象里填充这个集合，而不会产生新的数据库查询。
                # 这一步是解决问题的关键，因为它确保了在 session关闭前，关系被完全建立。
                for p in all_partitions:
                    # `len()` 是一个访问集合的简单无害方法
                    len(p.children)
                
                # 3. 筛选出顶层分区（没有父级的分区）并返回
                top_level_partitions = [p for p in all_partitions if p.parent_id is None]
                
                return top_level_partitions
            except Exception as e:
                log.error(f"获取分区树失败: {e}", exc_info=True)
                return []

    def add_partition(self, name, parent_id=None):
        """添加新分区，可以是顶层分区或子分区。"""
        with self.Session() as session:
            try:
                new_partition = Partition(name=name, parent_id=parent_id)
                session.add(new_partition)
                session.commit()
                session.refresh(new_partition)
                return new_partition
            except Exception as e:
                log.error(f"添加分区失败: {e}", exc_info=True)
                session.rollback()
                return None

    def rename_partition(self, partition_id, new_name):
        """重命名分区"""
        with self.Session() as session:
            try:
                partition = session.query(Partition).get(partition_id)
                if partition:
                    partition.name = new_name
                    session.commit()
                return True
            except Exception as e:
                log.error(f"重命名分区失败: {e}")
                session.rollback()
                return False

    def _get_all_descendant_ids(self, session, partition_id):
        """优化：使用递归CTE（公共表表达式）来高效地获取一个分区及其所有子孙分区的ID列表。"""
        # 定义递归查询的起始部分
        partition_cte = session.query(Partition.id).filter(Partition.id == partition_id).cte(name="partition_cte", recursive=True)
        
        # 定义递归部分
        partition_cte = partition_cte.union_all(
            session.query(Partition.id).filter(Partition.parent_id == partition_cte.c.id)
        )
        
        # 执行查询并提取ID
        all_ids = session.query(partition_cte.c.id).all()
        return [i[0] for i in all_ids]

    def delete_partition(self, partition_id):
        """递归删除一个分区及其所有子分区，并将所有包含的项目移至回收站。"""
        with self.Session() as session:
            try:
                partition_to_delete = session.query(Partition).get(partition_id)
                if not partition_to_delete:
                    return False

                # 1. 找到该分区及其所有子孙分区
                all_ids_to_process = self._get_all_descendant_ids(session, partition_id)
                
                # 2. 将这些分区下的所有项目移到回收站
                item_ids_to_trash_q = session.query(ClipboardItem.id).filter(ClipboardItem.partition_id.in_(all_ids_to_process))
                item_ids_to_trash = [i[0] for i in item_ids_to_trash_q.all()]
                if item_ids_to_trash:
                    self.move_items_to_trash(item_ids_to_trash)
                
                # 3. 删除顶层分区，cascade="all, delete-orphan" 会自动删除所有子孙分区记录
                session.delete(partition_to_delete)
                session.commit()
                return True
            except Exception as e:
                log.error(f"递归删除分区失败: {e}")
                session.rollback()
                return False

    def set_partition_tags(self, partition_id, tag_names):
        """为一个分区设置预设标签"""
        with self.Session() as session:
            try:
                partition = session.query(Partition).options(joinedload(Partition.tags)).get(partition_id)
                if not partition: return
                partition.tags.clear()
                for name in [name.strip() for name in tag_names if name.strip()]:
                    tag = session.query(Tag).filter_by(name=name).first() or Tag(name=name)
                    session.add(tag)
                    if tag not in partition.tags:
                        partition.tags.append(tag)
                session.commit()
            except Exception as e:
                log.error(f"设置分区标签失败: {e}")
                session.rollback()
    
    def get_partition_tags(self, partition_id):
        """获取一个分区的所有预设标签"""
        with self.Session() as session:
            try:
                partition = session.query(Partition).options(joinedload(Partition.tags)).get(partition_id)
                return [tag.name for tag in partition.tags] if partition else []
            except Exception as e:
                log.error(f"获取分区标签失败: {e}")
                return []

    def update_partition(self, partition_id, **kwargs):
        """更新分区属性（例如名称、颜色、父级、排序）"""
        with self.Session() as session:
            try:
                partition = session.query(Partition).get(partition_id)
                if partition:
                    for k, v in kwargs.items():
                        setattr(partition, k, v)
                    session.commit()
                return True
            except Exception as e:
                log.error(f"更新分区失败: {e}")
                session.rollback()
                return False

    def get_partition_item_counts(self):
        """获取每个分区的项目计数，并递归计算父分区的总数。"""
        with self.Session() as session:
            try:
                # 优化: 一次性查询所有非删除项目，然后在内存中处理计数
                base_query = session.query(ClipboardItem).filter(ClipboardItem.is_deleted != True)
                
                # 1. 直接获取每个分区的项目数 (partition_id -> count)
                direct_counts = dict(base_query.with_entities(
                    ClipboardItem.partition_id, func.count(ClipboardItem.id)
                ).group_by(ClipboardItem.partition_id).all())
                
                # 2. 未分类计数
                uncategorized_count = direct_counts.pop(None, 0)
                
                # 3. 递归计算总数
                total_counts = direct_counts.copy()
                all_partitions = session.query(Partition).all()
                partition_map = {p.id: p for p in all_partitions}

                # 从子节点向父节点累加计数
                for p in all_partitions:
                    direct_count = direct_counts.get(p.id, 0)
                    if direct_count > 0:
                        parent = partition_map.get(p.parent_id)
                        while parent:
                            total_counts[parent.id] = total_counts.get(parent.id, 0) + direct_count
                            parent = partition_map.get(parent.parent_id)
                
                # 新增：统计今日更新的数据
                now = datetime.now()
                today_start = datetime.combine(now.date(), time.min)
                today_modified_count = base_query.filter(ClipboardItem.modified_at >= today_start).count()

                # 5. 计算总数
                total_count = base_query.count()

                counts = {
                    'total': total_count, # 新增: 总项目数
                    'partitions': total_counts,
                    'uncategorized': uncategorized_count,
                    'untagged': base_query.filter(~exists().where(item_tags.c.item_id == ClipboardItem.id)).count(),
                    'trash': session.query(func.count(ClipboardItem.id)).filter(ClipboardItem.is_deleted == True).scalar(),
                    'today_modified': today_modified_count
                }
                return counts
            except Exception as e:
                log.error(f"获取分区项目计数失败: {e}", exc_info=True)
                return {'partitions': {}, 'uncategorized': 0, 'untagged': 0, 'trash': 0, 'today_modified': 0}

    def move_items_to_partition(self, item_ids, partition_id):
        """将多个项目批量移动到指定分区"""
        with self.Session() as session:
            try:
                session.query(ClipboardItem).filter(
                    ClipboardItem.id.in_(item_ids)
                ).update({'partition_id': partition_id}, synchronize_session=False)
                session.commit()
                log.info(f"成功将 {len(item_ids)} 个项目移动到分区 {partition_id}")
                return True
            except Exception as e:
                log.error(f"移动项目到分区失败: {e}", exc_info=True)
                session.rollback()
                return False

    def restore_and_move_items(self, item_ids, target_partition_id):
        """恢复项目并将其移动到指定分区。"""
        with self.Session() as session:
            try:
                items_to_restore = session.query(ClipboardItem).filter(ClipboardItem.id.in_(item_ids)).all()
                if not items_to_restore:
                    return False
                
                for item in items_to_restore:
                    item.is_deleted = False
                    item.partition_id = target_partition_id
                    item.original_partition_id = None
                
                session.commit()
                log.info(f"成功恢复并移动 {len(item_ids)} 个项目到分区 {target_partition_id}")
                return True
            except Exception as e:
                log.error(f"恢复并移动项目失败: {e}", exc_info=True)
                session.rollback()
                return False
