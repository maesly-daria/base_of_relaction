import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base_relaction.settings')
django.setup()

from recreation.models import Post, CustomUser
from django.db import connection, transaction
import sqlite3

def debug_post_save():
    print("=== ДИАГНОСТИКА СОХРАНЕНИЯ ПОСТА ===")
    
    post = Post.objects.get(id=1)
    print(f"Пост: {post.title}")
    print(f"Автор ID: {post.author_id}")
    
    # Проверим автора
    try:
        author = CustomUser.objects.get(id=post.author_id)
        print(f"✅ Автор существует: {author}")
    except CustomUser.DoesNotExist:
        print(f"❌ Автор с ID {post.author_id} не существует!")
        return
    
    # Попробуем простое сохранение
    print("\n1. Простое сохранение:")
    try:
        post.save()
        print("✅ Простое сохранение успешно")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    # Попробуем сохранение с явным указанием полей
    print("\n2. Сохранение с указанием полей:")
    try:
        with transaction.atomic():
            Post.objects.filter(id=post.id).update(
                title=post.title,
                author_id=post.author_id,
                status=post.status
            )
        print("✅ Сохранение через update успешно")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    # Проверим SQLite напрямую
    print("\n3. Проверка через SQLite:")
    try:
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        
        # Включим foreign keys
        cursor.execute("PRAGMA foreign_keys=ON;")
        
        # Попробуем обновить запись
        cursor.execute("""
            UPDATE recreation_post 
            SET title = ?, author_id = ?, status = ?
            WHERE id = ?
        """, (post.title, post.author_id, post.status, post.id))
        
        conn.commit()
        print("✅ Прямое SQL обновление успешно")
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка SQL: {e}")

if __name__ == "__main__":
    debug_post_save()