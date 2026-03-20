"""
Диагностика UI Automation — ищем поле страницы в SumatraPDF.
Запусти пока SumatraPDF открыт.

Запуск: python debug_uia.py
"""
import sys

try:
    import comtypes.client
except ImportError:
    print("Устанавливаю comtypes...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "comtypes"])
    import comtypes.client

import comtypes
import comtypes.gen
import win32gui

# Загружаем UIAutomation
UIA = comtypes.client.GetModule("UIAutomationCore.dll")
IUIAutomation = comtypes.client.CreateObject("{ff48dba4-60ef-4201-aa87-54103eef594e}",
                                              interface=UIA.IUIAutomation)

def find_sumatra_hwnd():
    result = []
    def cb(hwnd, _):
        title = win32gui.GetWindowText(hwnd)
        if 'SumatraPDF' in title and win32gui.IsWindowVisible(hwnd):
            result.append((hwnd, title))
        return True
    win32gui.EnumWindows(cb, None)
    return result

def dump_element(el, depth=0, max_depth=4):
    if depth > max_depth:
        return
    try:
        name       = el.CurrentName or ""
        ctrl_type  = el.CurrentControlType
        value_pat  = None
        try:
            value_pat = el.GetCurrentPattern(UIA.UIA_ValuePatternId)
            value_pat = value_pat.QueryInterface(UIA.IUIAutomationValuePattern)
            val = value_pat.CurrentValue
        except Exception:
            val = ""

        indent = "  " * depth
        line = f"{indent}[{ctrl_type}] name={repr(name)}"
        if val:
            line += f"  VALUE={repr(val)}"
        print(line)
    except Exception as e:
        print("  " * depth + f"(ошибка: {e})")
        return

    try:
        child = el.GetFirstChildElement(IUIAutomation.ControlViewWalker)
        while child:
            dump_element(child, depth + 1, max_depth)
            child = IUIAutomation.ControlViewWalker.GetNextSiblingElement(child)
    except Exception:
        pass

print("Ищем SumatraPDF...")
windows = find_sumatra_hwnd()
if not windows:
    print("SumatraPDF не найден! Убедись что он открыт.")
    input("Enter для выхода...")
    sys.exit(1)

for hwnd, title in windows:
    print(f"\nОкно: {repr(title)}  hwnd={hwnd}")
    try:
        el = IUIAutomation.ElementFromHandle(hwnd)

        # Ищем все Edit и Spinner элементы (поле ввода страницы)
        print("\n--- Все Edit/Spinner элементы (поля ввода) ---")
        cond_edit    = IUIAutomation.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId, UIA.UIA_EditControlTypeId)
        cond_spinner = IUIAutomation.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId, UIA.UIA_SpinnerControlTypeId)
        cond_or      = IUIAutomation.CreateOrCondition(cond_edit, cond_spinner)
        found = el.FindAll(UIA.TreeScope_Descendants, cond_or)
        if found and found.Length > 0:
            for i in range(found.Length):
                item = found.GetElement(i)
                name = item.CurrentName or ""
                try:
                    vp = item.GetCurrentPattern(UIA.UIA_ValuePatternId)
                    vp = vp.QueryInterface(UIA.IUIAutomationValuePattern)
                    val = vp.CurrentValue
                except Exception:
                    val = "?"
                print(f"  Edit/Spinner: name={repr(name)}  value={repr(val)}")
        else:
            print("  (не найдено)")

        # Дамп первых уровней дерева
        print("\n--- Дерево элементов (4 уровня) ---")
        dump_element(el)

    except Exception as e:
        print(f"Ошибка UIA: {e}")

input("\nГотово. Нажми Enter для выхода...")
