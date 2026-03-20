"""
Диагностика: показывает заголовки всех открытых окон.
Запусти этот скрипт пока SumatraPDF открыт с PDF-файлом.

Запуск: python debug_windows.py
"""

import sys

try:
    import win32gui
except ImportError:
    print("ОШИБКА: pywin32 не установлен.")
    print("Выполни: pip install pywin32")
    input("\nНажми Enter для выхода...")
    sys.exit(1)

titles = []

def callback(hwnd, _):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if title.strip():
            titles.append(title)
    return True

win32gui.EnumWindows(callback, None)

print("=" * 60)
print("Все видимые окна:")
print("=" * 60)
for t in titles:
    print(repr(t))

print("=" * 60)
print("\nОкна содержащие 'PDF' или 'Sumatra' (без учёта регистра):")
found = [t for t in titles if 'pdf' in t.lower() or 'sumatra' in t.lower()]
if found:
    for t in found:
        print("  >>", repr(t))
else:
    print("  (не найдено)")

input("\nНажми Enter для выхода...")
