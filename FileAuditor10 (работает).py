import os
import sys
import subprocess
import getpass
import time
import threading
from datetime import datetime
from pathlib import Path

# --- 1. АВТОМАТИЧЕСКАЯ УСТАНОВКА ЗАВИСИМОСТЕЙ ---
# В этой версии зависимостей нет.
# required_packages = []
# for package in required_packages:
#     try:
#         __import__(package)
#     except ImportError:
#         print(f"📦 Установка необходимого пакета: {package}...")
#         subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", package])
#         print(f"✅ {package} установлен успешно.")

# --- АНИМАЦИЯ ЗАГРУЗКИ ---
def animate_scanning(active_flag):
    for c in r'-\|/-\|/':
        if not active_flag[0]:
            break
        print(f"\r🔍 Сканирование: {c}", end='', flush=True)
        time.sleep(0.1)
    print("\r" + " " * 25, end='\r', flush=True)

class FileAuditor:
    SEARCH_TERMS = [
        'пдн', 'паспорт', 'снилс', 'инн', 'договор', 'закупка', 'контракт',
        'билеты', 'медкнижка', 'диплом', 'удостоверение', 'фио', 'фамилия',
        'имя', 'отчество'
    ]
    FILE_ICONS = {
        '.pdf': '📄', '.doc': '📝', '.docx': '📝', '.xls': '📊', '.xlsx': '📊',
        '.jpg': '📷', '.jpeg': '📷', '.png': '🎨', '.txt': '📋', '.zip': '🗃️', '.rar': '🗃️'
    }
    def __init__(self, shared_folder_path):
        self.shared_folder_path = shared_folder_path.replace('\\', '/')
        self.results = []
        self.errors = []
    def scan_folder(self):
        check_path = self.shared_folder_path.replace('/', '\\')
        if not os.path.exists(check_path):
            error_msg = f"Ошибка: Путь {check_path} не существует или недоступен."
            print(error_msg)
            self.errors.append(error_msg)
            return
        print(f"Начинаем сканирование папки: {check_path}")
        anim_active = [True]
        anim_thread = threading.Thread(target=animate_scanning, args=(anim_active,))
        anim_thread.start()
        try:
            for root, dirs, files in os.walk(check_path):
                for file in files:
                    print(f"\r🔎 Проверяю файл: {os.path.join(root, file)}", end='', flush=True)
                    try:
                        self._check_file(root, file)
                    except Exception as e:
                        error_msg = f"⚠️ Ошибка при обработке файла '{file}': {e}"
                        print("\n" + error_msg)
                        self.errors.append(error_msg)
                print("\r" + " " * 60, end='\r', flush=True)
                for i in range(len(dirs) - 1, -1, -1):
                    dir_path = os.path.join(root, dirs[i])
                    if not os.access(dir_path, os.R_OK):
                        print(f"⚠️ Нет доступа к папке: {dir_path}. Пропуск.")
                        dirs.pop(i)
                        self.errors.append(f"Нет доступа к папке: {dir_path}")
        except PermissionError as e:
            error_msg = f"❗ Нет прав на сканирование: {e}"
            print("\n" + error_msg)
            self.errors.append(error_msg)
            anim_active[0] = False
            anim_thread.join()
            return
        except Exception as e:
            error_msg = f"❗ Критическая ошибка: {e}"
            print("\n" + error_msg)
            self.errors.append(error_msg)
            anim_active[0] = False
            anim_thread.join()
            return
        finally:
            anim_active[0] = False
            anim_thread.join()
            print("\rСканирование завершено. " + " " * 40)
    def _get_file_owner(self, full_path):
        try:
            return getpass.getuser()
        except Exception:
            return "Неизвестно"
    def _get_file_icon(self, filename):
        ext = Path(filename).suffix.lower()
        return self.FILE_ICONS.get(ext, '📁')
    def _check_file(self, folder_path, filename):
        filename_lower = filename.lower()
        for term in self.SEARCH_TERMS:
            if term in filename_lower:
                full_path = os.path.join(folder_path, filename)
                try:
                    file_size = os.path.getsize(full_path)
                    last_modified = datetime.fromtimestamp(os.path.getmtime(full_path))
                    created_time = datetime.fromtimestamp(os.path.getctime(full_path))
                    owner = self._get_file_owner(full_path)
                    last_editor = "Неизвестно"
                    icon = self._get_file_icon(filename)
                    self.results.append({
                        'filename': filename,
                        'path': full_path,
                        'size_kb': round(file_size / 1024, 2),
                        'last_modified': last_modified,
                        'created': created_time,
                        'owner': owner,
                        'last_editor': last_editor,
                        'keyword_found': term,
                        'icon': icon
                    })
                    break
                except (OSError, IOError) as e:
                    error_msg = f"❌ Ошибка доступа к файлу '{full_path}': {e}"
                    print("\n" + error_msg)
                    self.errors.append(error_msg)
    def _generate_report(self):
        print("\n" + "=" * 80)
        print("🔍 ОТЧЁТ О РЕЗУЛЬТАТАХ АУДИТА")
        print("=" * 80)
        if self.errors:
            print("⚠️ ОБНАРУЖЕНЫ ОШИБКИ:")
            for i, error in enumerate(self.errors, 1):
                print(f"{i}. {error}")
            print()
        has_data = len(self.results) > 0 or len(self.errors) > 0
        if not has_data:
            print("ℹ️ Папка пуста или не содержит файлов для проверки.")
            return
        if self.results:
            print(f"✅ Найдено файлов: {len(self.results)}")
            print("-" * 80)
            sorted_results = sorted(self.results, key=lambda x: x['last_modified'], reverse=True)
            for i, item in enumerate(sorted_results, 1):
                print(f"{i}. {item['icon']} Файл: {item['filename']}")
                print(f"   📂 Путь: {item['path']}")
                print(f"   💾 Размер: {item['size_kb']} KB")
                print(f"   🗓️ Создан: {item['created'].strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   ⏱️ Последнее изменение: {item['last_modified'].strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   👤 Владелец: {item['owner']}")
                print(f"   ✍️ Последний редактор: {item['last_editor']}")
                print(f"   🔍 Найдено по ключевому слову: '{item['keyword_found']}'\n")
    def save_to_txt(self):
        script_dir = Path(__file__).parent
        report_filename = script_dir / "audit_report.txt"
        if len(self.results) == 0 and len(self.errors) == 0:
            return
        try:
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("🔍 ОТЧЁТ О РЕЗУЛЬТАТАХ АУДИТА\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Путь к папке: {self.shared_folder_path}\n")
                f.write(f"Пользователь: {getpass.getuser()}\n")
                f.write(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                if self.errors:
                    f.write("⚠️ ОШИБКИ:\n")
                    for error in self.errors:
                        f.write(f"- {error}\n")
                    f.write("\n")
                if self.results:
                    f.write("✅ НАЙДЕНО ФАЙЛОВ:\n")
                    sorted_results = sorted(self.results, key=lambda x: x['last_modified'], reverse=True)
                    for item in sorted_results:
                        f.write(f"{item['icon']} Файл: {item['filename']}\n")
                        f.write(f"Путь: {item['path']}\n")
                        f.write(f"Размер: {item['size_kb']} KB\n")
                        f.write(f"Создан: {item['created'].strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"Изменен: {item['last_modified'].strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"Владелец: {item['owner']}\n")
                        f.write(f"Ключевое слово: '{item['keyword_found']}'\n\n")
                f.write("=" * 80 + "\nКонец отчёта\n")
            print(f"✅ Отчёт успешно сохранён в файл: {report_filename}")
        except Exception as e:
            print(f"❌ Ошибка при сохранении отчёта: {e}")
def show_description():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 50)
    print("🛡️ FileAuditor v1.4 - Краткое описание")
    print("=" * 50)
    print("Программа ищет файлы с чувствительными данными (ФИО, паспорт и др.) в именах.")
    input("\nНажмите Enter для возврата в меню...")
def main():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 45)
        print("🛡️ FileAuditor v1.4 - Главное меню")
        print("=" * 45)
        print("[1] Запустить аудит папки")
        print("[2] О программе (описание)")
        print("[3] Выход")
        choice = input("Выберите действие (1/2/3): ").strip()
        if choice == '1':
            folder_path = input("\nВведите путь к папке (или оставьте пустым для выхода): ").strip()
            if not folder_path or folder_path.lower() == 'выход':
                continue
            auditor = FileAuditor(folder_path)
            auditor.scan_folder()
            auditor._generate_report()
            auditor.save_to_txt()
            input("\nНажмите Enter для возврата в меню...")
        elif choice == '2':
            show_description()
        elif choice == '3':
            print("До свидания! Спасибо за использование.")
            break

if __name__ == "__main__":
    main()