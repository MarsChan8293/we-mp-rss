#!/usr/bin/env python3
"""
数据库迁移脚本：为 message_tasks 表添加邮箱字段
执行方式：python migrations/add_message_task_email_fields.py
"""
from sqlalchemy import inspect, text

from core.db import DB
from core.print import print_error, print_info, print_success


def migrate():
    """执行数据库迁移"""
    print_info("开始迁移：为 message_tasks 表添加邮箱字段")

    engine = DB.get_engine()
    session = DB.get_session()

    try:
        inspector = inspect(engine)
        if "message_tasks" not in inspector.get_table_names():
            print_error("message_tasks 表不存在，跳过迁移")
            return

        columns = {col["name"] for col in inspector.get_columns("message_tasks")}
        field_sql = {
            "email_to": "ALTER TABLE message_tasks ADD COLUMN email_to TEXT",
            "email_cc": "ALTER TABLE message_tasks ADD COLUMN email_cc TEXT",
            "email_subject_template": "ALTER TABLE message_tasks ADD COLUMN email_subject_template TEXT",
            "email_content_type": "ALTER TABLE message_tasks ADD COLUMN email_content_type VARCHAR(20)",
        }

        for field_name, sql in field_sql.items():
            if field_name in columns:
                print_info(f"{field_name} 字段已存在，跳过")
                continue

            print_info(f"添加 {field_name} 字段...")
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
            print_success(f"{field_name} 字段添加成功")

        print_success("数据库迁移完成！")
    except Exception as e:
        print_error(f"数据库迁移失败: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate()
