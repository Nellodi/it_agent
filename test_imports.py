#!/usr/bin/env python3
# Тестовый скрипт для проверки импортов

try:
    print("1. Проверка импорта database...")
    from database import (
        get_all_tickets, get_ticket_history, assign_ticket_to_admin,
        update_ticket_status, get_user_role, get_user_equipment, get_user_tickets
    )
    print("   ✓ database успешно импортирован")
    
    print("2. Проверка импорта auth_checks...")
    from utils.auth_checks import is_admin, is_super_admin
    print("   ✓ auth_checks успешно импортирован")
    
    print("3. Проверка импорта inventory_generator...")
    from utils.inventory_generator import generate_inventory_number, get_available_categories
    print("   ✓ inventory_generator успешно импортирован")
    
    print("4. Проверка импорта handlers...")
    from handlers import (
        auth, start, profile, tickets, admin, admin_tickets, equipment, workplaces
    )
    print("   ✓ Все handlers успешно импортированы")
    
    print("\n✅ ВСЕ ИМПОРТЫ УСПЕШНЫ!")
    print("Бот готов к запуску.")
    
except ImportError as e:
    print(f"\n❌ ОШИБКА ИМПОРТА: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"\n❌ НЕОЖИДАННАЯ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()
