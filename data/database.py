# -*- coding: utf-8 -*-
import sys
import os
import shutil
import hashlib
import logging
from datetime import datetime, timedelta, time
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Table, Index, Float, func, or_, exists, and_, BLOB
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, joinedload

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
    parent_id = Column(Integer, ForeignKey('partitions.id'), nullable=True)
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
    is_deleted = Column(Boolean, default=False, index=True)
    custom_color = Column(String(20), default=None)
    is_file = Column(Boolean, default=False)
    file_path = Column(Text, default=None)
    item_type = Column(String(20), default='text')
    image_path = Column(Text, default=None)
    data_blob = Column(BLOB, nullable=True)
    thumbnail_blob = Column(BLOB, nullable=True)
    partition_id = Column(Integer, ForeignKey('partitions.id'), nullable=True)
    original_partition_id = Column(Integer, nullable=True)
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
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
            self._check_migrations()
        except Exception as e:
            log.critical(f"数据库初始化失败: {e}", exc_info=True)

    def _check_migrations(self):
        from sqlalchemy import inspect, text
        try:
            log.info("通用迁移检查：使用 SQLAlchemy Inspector")
            inspector = inspect(self.engine)
            
            with self.engine.connect() as connection:
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

                if inspector.has_table("partition_groups"):
                    log.info("检测到需要数据迁移的旧表结构 (partition_groups)。")

                    # --- 数据库备份 ---
                    db_path = self.engine.url.database
                    backup_path = f"{db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    try:
                        log.info(f"正在备份当前数据库到: {backup_path}")
                        shutil.copy2(db_path, backup_path)
                        log.info("✅ 数据库备份成功。")
                    except Exception as backup_exc:
                        log.critical(f"❌ 数据库备份失败: {backup_exc}", exc_info=True)
                        log.critical("为防止数据丢失，迁移操作已中止。请手动备份数据库文件后再试。")
                        raise  # 阻止迁移继续进行

                    log.info("开始数据迁移...")
                    migration_transaction = connection.begin()
                    try:
                        groups = connection.execute(text("SELECT id, name, color, sort_index FROM partition_groups ORDER BY id")).fetchall()
                        group_tags_results = connection.execute(text("SELECT partition_group_id, tag_id FROM partition_group_tags")).fetchall()
                        group_tags_map = {}
                        for group_id, tag_id in group_tags_results:
                            group_tags_map.setdefault(group_id, []).append(tag_id)

                        for old_group_id, name, color, sort_index in groups:
                            result = connection.execute(text(
                                "INSERT INTO partitions (name, color, sort_index, parent_id) VALUES (:name, :color, :sort_index, NULL)"
                            ), {"name": name, "color": color, "sort_index": sort_index})
                            
                            new_parent_id = result.lastrowid
                            log.info(f"  - 分组 '{name}' (ID:{old_group_id}) 已迁移为顶层分区 (ID:{new_parent_id})")

                            update_stmt = text("UPDATE partitions SET parent_id = :parent_id WHERE group_id = :group_id")
                            connection.execute(update_stmt, {"parent_id": new_parent_id, "group_id": old_group_id})

                            if old_group_id in group_tags_map:
                                for tag_id in group_tags_map[old_group_id]:
                                    connection.execute(text(
                                        "INSERT INTO partition_tags (partition_id, tag_id) VALUES (:p_id, :t_id)"
                                    ), {"p_id": new_parent_id, "t_id": tag_id})
                                log.info(f"    - 成功迁移 {len(group_tags_map[old_group_id])} 个标签")

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

    def get_session(self):
        return self.Session()

    def add_item(self, text, is_file=False, file_path=None, item_type='text', image_path=None, partition_id=None, data_blob=None, thumbnail_blob=None):
        session = self.get_session()
        try:
            # --- 输入验证 ---
            if text is None:
                log.warning("尝试添加内容为 None 的项目，已跳过。")
                return None, False

            # --- 大小限制 ---
            MAX_TEXT_SIZE = 10 * 1024 * 1024  # 10MB
            try:
                text_bytes = text.encode('utf-8')
                if len(text_bytes) > MAX_TEXT_SIZE:
                    log.warning(f"内容过大 ({len(text_bytes)} bytes)，将被截断为 {MAX_TEXT_SIZE} bytes。")
                    # 截断时需要注意不要破坏多字节字符
                    text = text[:MAX_TEXT_SIZE // 4]
                    text_bytes = text.encode('utf-8', 'ignore')
            except Exception as enc_e:
                log.error(f"文本编码失败: {enc_e}, text: {str(text)[:100]}")
                return None, False

            text_hash = hashlib.sha256(text_bytes).hexdigest()
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
                content=text, content_hash=text_hash, sort_index=new_sort, note=note_txt,
                is_file=is_file, file_path=file_path, item_type=item_type, image_path=image_path,
                partition_id=partition_id, data_blob=data_blob, thumbnail_blob=thumbnail_blob
            )
            session.add(new_item)
            try:
                session.commit()
                session.refresh(new_item)
                return new_item, True
            except Exception:
                session.rollback()
                existing = session.query(ClipboardItem).filter_by(content_hash=text_hash).first()
                if existing:
                    existing.last_visited_at = datetime.now()
                    existing.visit_count += 1
                    session.commit()
                    return existing, False
                return None, False
        except Exception as e:
            log.error(f"写入失败: {e}")
            session.rollback()
            return None, False
        finally:
            session.close()

    def _build_query(self, session, sort_mode="manual", date_filter=None, date_modify_filter=None, partition_filter=None, include_deleted=False):
        log.debug(f"🔍 构建查询: sort={sort_mode}, date={date_filter}, date_modify={date_modify_filter}, partition={partition_filter}, deleted={include_deleted}")
        q = session.query(ClipboardItem).options(
            joinedload(ClipboardItem.tags),
            joinedload(ClipboardItem.partition)
        )
        if include_deleted:
            q = q.filter(ClipboardItem.is_deleted == True)
        else:
            q = q.filter(ClipboardItem.is_deleted != True)
        
        if partition_filter:
            ptype = partition_filter.get('type')
            pid = partition_filter.get('id')
            if ptype == 'partition':
                q = q.filter(ClipboardItem.partition_id.in_(self._get_all_descendant_ids(session, pid)))
            elif ptype == 'uncategorized':
                q = q.filter(ClipboardItem.partition_id == None)
            elif ptype == 'untagged':
                q = q.filter(~exists().where(item_tags.c.item_id == ClipboardItem.id))
        
        def apply_date_filter(query, column, filter_str):
            if not filter_str:
                return query
            today = datetime.now().date()
            start_dt, end_dt = None, None
            if filter_str == "今日":
                start_dt, end_dt = datetime.combine(today, time.min), datetime.combine(today, time.max)
            elif filter_str == "昨日":
                start_dt, end_dt = datetime.combine(today - timedelta(days=1), time.min), datetime.combine(today - timedelta(days=1), time.max)
            elif filter_str == "周内":
                start_dt = datetime.combine(today - timedelta(days=7), time.min)
            elif filter_str == "两周":
                start_dt = datetime.combine(today - timedelta(days=14), time.min)
            elif filter_str == "本月":
                start_dt = datetime.combine(today.replace(day=1), time.min)
            elif filter_str == "上月":
                first_day = today.replace(day=1)
                last_month_end = first_day - timedelta(days=1)
                start_dt, end_dt = datetime.combine(last_month_end.replace(day=1), time.min), datetime.combine(last_month_end, time.max)
            
            if start_dt:
                query = query.filter(column >= start_dt)
            if end_dt:
                query = query.filter(column <= end_dt)
            return query

        q = apply_date_filter(q, ClipboardItem.created_at, date_filter)
        q = apply_date_filter(q, ClipboardItem.modified_at, date_modify_filter)
            
        if sort_mode == "manual":
            q = q.order_by(ClipboardItem.is_pinned.desc(), ClipboardItem.sort_index.asc())
        elif sort_mode == "time":
            q = q.order_by(ClipboardItem.is_pinned.desc(), ClipboardItem.created_at.desc())
        return q

    def get_items(self, sort_mode="manual", limit=50, offset=0, date_filter=None, date_modify_filter=None, partition_filter=None):
        session = self.get_session()
        try:
            include_deleted = (partition_filter and partition_filter.get('type') == 'trash')
            q = self._build_query(session, sort_mode=sort_mode, date_filter=date_filter, date_modify_filter=date_modify_filter, partition_filter=partition_filter, include_deleted=include_deleted)
            if limit is not None:
                q = q.limit(limit)
            if offset > 0:
                q = q.offset(offset)
            return q.all()
        except Exception as e:
            log.error(f"查询失败: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def get_items_detached(self, sort_mode="manual", limit=50, offset=0, date_filter=None, date_modify_filter=None, partition_filter=None):
        """
        获取脱离 session 的对象，使其可以在 UI 线程中安全使用。
        """
        session = self.get_session()
        try:
            include_deleted = (partition_filter and partition_filter.get('type') == 'trash')
            q = self._build_query(session, sort_mode=sort_mode, date_filter=date_filter, date_modify_filter=date_modify_filter, partition_filter=partition_filter, include_deleted=include_deleted)

            if limit is not None:
                q = q.limit(limit)
            if offset > 0:
                q = q.offset(offset)

            items = q.all()

            # 急切加载所有关联数据并脱离 session
            for item in items:
                # 访问关联属性以确保它们被加载
                _ = len(item.tags)
                _ = item.partition
                session.expunge(item)

            return items
        except Exception as e:
            log.error(f"查询 (detached) 失败: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def get_count(self, date_filter=None, date_modify_filter=None, partition_filter=None):
        session = self.get_session()
        try:
            include_deleted = (partition_filter and partition_filter.get('type') == 'trash')
            q = self._build_query(session, date_filter=date_filter, date_modify_filter=date_modify_filter, partition_filter=partition_filter, include_deleted=include_deleted)
            return q.count()
        except Exception as e:
            log.error(f"计数失败: {e}", exc_info=True)
            return 0
        finally:
            session.close()

    def update_item(self, item_id, **kwargs):
        session = self.get_session()
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
        finally:
            session.close()

    def move_items_to_trash(self, ids):
        session = self.get_session()
        try:
            items = session.query(ClipboardItem).filter(ClipboardItem.id.in_(ids), ClipboardItem.is_locked == False).all()
            for item in items:
                item.original_partition_id = item.partition_id
                item.partition_id = None
                item.is_deleted = True
            session.commit()
        except Exception as e:
            log.error(f"移动到回收站失败: {e}")
            session.rollback()
        finally:
            session.close()

    def restore_items_from_trash(self, ids):
        session = self.get_session()
        try:
            items = session.query(ClipboardItem).filter(ClipboardItem.id.in_(ids)).all()
            if not items:
                return
            existing_pids = {p_id for p_id, in session.query(Partition.id).all()}
            for item in items:
                item.is_deleted = False
                item.partition_id = item.original_partition_id if item.original_partition_id in existing_pids else None
                item.original_partition_id = None
            session.commit()
        except Exception as e:
            log.error(f"从回收站恢复失败: {e}")
            session.rollback()
        finally:
            session.close()

    def delete_items_permanently(self, ids):
        session = self.get_session()
        try:
            session.query(ClipboardItem).filter(ClipboardItem.id.in_(ids)).delete(synchronize_session=False)
            session.commit()
        except Exception as e:
            log.error(f"永久删除失败: {e}")
            session.rollback()
        finally:
            session.close()

    def update_sort_order(self, ids):
        session = self.get_session()
        try:
            for idx, i in enumerate(ids):
                item = session.query(ClipboardItem).get(i)
                if item:
                    item.sort_index = float(idx)
            session.commit()
        except Exception as e:
            log.error(f"更新排序失败: {e}")
            session.rollback()
        finally:
            session.close()

    def get_stats(self):
        stats = {'tags': [], 'stars': {}, 'colors': {}, 'types': {}}
        session = self.get_session()
        try:
            last_used = func.max(ClipboardItem.modified_at).label("last_used")
            stats['tags'] = session.query(Tag.name, func.count(item_tags.c.item_id)).outerjoin(item_tags).outerjoin(ClipboardItem).group_by(Tag.id).order_by(last_used.desc()).all()
            stats['stars'] = {s: c for s, c in session.query(ClipboardItem.star_level, func.count(ClipboardItem.id)).group_by(ClipboardItem.star_level).all()}
            stats['colors'] = {c: count for c, count in session.query(ClipboardItem.custom_color, func.count(ClipboardItem.id)).group_by(ClipboardItem.custom_color).all() if c}
            return stats
        except Exception as e:
            log.error(f"获取统计失败: {e}", exc_info=True)
            return stats
        finally:
            session.close()

    def get_stats_for_items(self, item_ids):
        """为给定的 item_ids 列表高效计算统计数据"""
        stats = {'tags': {}, 'stars': {}, 'colors': {}, 'types': {}}
        if not item_ids:
            return stats

        session = self.get_session()
        try:
            # 标签统计
            tag_counts = session.query(Tag.name, func.count(item_tags.c.item_id))\
                .join(item_tags)\
                .filter(item_tags.c.item_id.in_(item_ids))\
                .group_by(Tag.name)\
                .all()
            stats['tags'] = dict(tag_counts)

            # 星级、颜色、类型统计
            base_query = session.query(ClipboardItem).filter(ClipboardItem.id.in_(item_ids))

            star_counts = base_query.with_entities(ClipboardItem.star_level, func.count(ClipboardItem.id))\
                .group_by(ClipboardItem.star_level)\
                .all()
            stats['stars'] = dict(star_counts)

            color_counts = base_query.with_entities(ClipboardItem.custom_color, func.count(ClipboardItem.id))\
                .filter(ClipboardItem.custom_color.isnot(None))\
                .group_by(ClipboardItem.custom_color)\
                .all()
            stats['colors'] = dict(color_counts)

            # 类型统计需要更复杂一点的逻辑，暂时保持原样，在UI层处理

            return stats
        except Exception as e:
            log.error(f"获取指定项目统计失败: {e}", exc_info=True)
            return stats
        finally:
            session.close()

    def add_tags_to_items(self, item_ids, tag_names):
        session = self.get_session()
        try:
            items = session.query(ClipboardItem).filter(ClipboardItem.id.in_(item_ids)).all()
            if not items:
                return
            for name in [name.strip() for name in tag_names if name.strip()]:
                tag = session.query(Tag).filter_by(name=name).first() or Tag(name=name)
                session.add(tag)
                session.flush()
                for item in items:
                    if tag not in item.tags:
                        item.tags.append(tag)
            session.commit()
        except Exception as e:
            log.error(f"批量添加标签失败: {e}")
            session.rollback()
        finally:
            session.close()

    def remove_tag_from_item(self, item_id, tag_name):
        session = self.get_session()
        try:
            item = session.query(ClipboardItem).get(item_id)
            tag = session.query(Tag).filter_by(name=tag_name).first()
            if item and tag and tag in item.tags:
                item.tags.remove(tag)
                session.commit()
        except Exception as e:
            log.error(f"移除标签失败: {e}")
            session.rollback()
        finally:
            session.close()

    def auto_delete_old_data(self, days=21):
        session = self.get_session()
        try:
            count = session.query(ClipboardItem).filter(
                ClipboardItem.created_at < datetime.now() - timedelta(days=days),
                ClipboardItem.is_locked == False
            ).delete(synchronize_session=False)
            session.commit()
            return count
        except Exception as e:
            log.error(f"清理旧数据失败: {e}")
            session.rollback()
            return 0
        finally:
            session.close()

    def get_partitions_tree(self):
        session = self.get_session()
        try:
            all_partitions = session.query(Partition).order_by(Partition.sort_index).all()
            for p in all_partitions:
                len(p.children)
            return [p for p in all_partitions if p.parent_id is None]
        except Exception as e:
            log.error(f"获取分区树失败: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def add_partition(self, name, parent_id=None):
        session = self.get_session()
        try:
            new_p = Partition(name=name, parent_id=parent_id)
            session.add(new_p)
            session.commit()
            session.refresh(new_p)
            return new_p
        except Exception as e:
            log.error(f"添加分区失败: {e}", exc_info=True)
            session.rollback()
            return None
        finally:
            session.close()

    def rename_partition(self, partition_id, new_name):
        session = self.get_session()
        try:
            p = session.query(Partition).get(partition_id)
            if p:
                p.name = new_name
                session.commit()
            return True
        except Exception as e:
            log.error(f"重命名分区失败: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def _get_all_descendant_ids(self, session, partition_id):
        cte = session.query(Partition.id).filter(Partition.id == partition_id).cte(name="cte", recursive=True)
        cte = cte.union_all(session.query(Partition.id).filter(Partition.parent_id == cte.c.id))
        return [i[0] for i in session.query(cte.c.id).all()]

    def delete_partition(self, partition_id):
        session = self.get_session()
        try:
            p_to_del = session.query(Partition).get(partition_id)
            if not p_to_del:
                return False
            all_ids = self._get_all_descendant_ids(session, partition_id)
            item_ids = [i[0] for i in session.query(ClipboardItem.id).filter(ClipboardItem.partition_id.in_(all_ids)).all()]
            if item_ids:
                self.move_items_to_trash(item_ids)
            session.delete(p_to_del)
            session.commit()
            return True
        except Exception as e:
            log.error(f"递归删除分区失败: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def update_partition(self, partition_id, **kwargs):
        session = self.get_session()
        try:
            p = session.query(Partition).get(partition_id)
            if p:
                for k, v in kwargs.items():
                    setattr(p, k, v)
                session.commit()
            return True
        except Exception as e:
            log.error(f"更新分区失败: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_partition_item_counts(self):
        session = self.get_session()
        try:
            base_q = session.query(ClipboardItem).filter(ClipboardItem.is_deleted != True)
            direct_counts = dict(base_q.with_entities(ClipboardItem.partition_id, func.count(ClipboardItem.id)).group_by(ClipboardItem.partition_id).all())
            uncategorized = direct_counts.pop(None, 0)
            total_counts = direct_counts.copy()
            partitions = session.query(Partition).all()
            p_map = {p.id: p for p in partitions}
            for p in partitions:
                direct_count = direct_counts.get(p.id, 0)
                if direct_count > 0:
                    parent = p_map.get(p.parent_id)
                    while parent:
                        total_counts[parent.id] = total_counts.get(parent.id, 0) + direct_count
                        parent = p_map.get(parent.parent_id)
            today_start = datetime.combine(datetime.now().date(), time.min)
            return {
                'total': base_q.count(),
                'partitions': total_counts,
                'uncategorized': uncategorized,
                'untagged': base_q.filter(~exists().where(item_tags.c.item_id == ClipboardItem.id)).count(),
                'trash': session.query(func.count(ClipboardItem.id)).filter(ClipboardItem.is_deleted == True).scalar(),
                'today_modified': base_q.filter(ClipboardItem.modified_at >= today_start).count()
            }
        except Exception as e:
            log.error(f"获取分区项目计数失败: {e}", exc_info=True)
            return {}
        finally:
            session.close()

    def move_items_to_partition(self, item_ids, partition_id):
        session = self.get_session()
        try:
            session.query(ClipboardItem).filter(ClipboardItem.id.in_(item_ids)).update({'partition_id': partition_id}, synchronize_session=False)
            session.commit()
            return True
        except Exception as e:
            log.error(f"移动项目到分区失败: {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

    def restore_and_move_items(self, item_ids, target_partition_id):
        session = self.get_session()
        try:
            items = session.query(ClipboardItem).filter(ClipboardItem.id.in_(item_ids)).all()
            if not items:
                return False
            for item in items:
                item.is_deleted = False
                item.partition_id = target_partition_id
                item.original_partition_id = None
            session.commit()
            return True
        except Exception as e:
            log.error(f"恢复并移动项目失败: {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()
