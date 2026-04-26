import os
import sys
import subprocess
import getpass
import time
import threading
from datetime import datetime
from pathlib import Path

# --- 1. АВТОМАТИЧЕСКАЯ УСТАНОВКА ЗАВИСИМОСТЕЙ ---
required_packages = ['colorama', 'pywin32']
for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        print(f"📦 Установка необходимого пакета: {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", package])
            print(f"✅ {package} установлен успешно.")
        except Exception as e:
            print(f"❌ Ошибка при установке {package}.")
            print(f"Детали ошибки: {e}")
            print("Пожалуйста, установите пакет вручную: pip install", package)
            sys.exit(1)

from colorama import init, Fore, Style
init(autoreset=True)  # Автоматический сброс цвета после каждого print

# --- АНИМАЦИЯ ЗАГРУЗКИ ---
def animate_scanning(active_flag):
    """Запускает анимацию загрузки, пока флаг active_flag[0] == True."""
    for c in r'-\|/-\|/':
        if not active_flag[0]:
            break
        print(f"\r{Fore.CYAN}🔍 Сканирование: {c}", end='', flush=True)
        time.sleep(0.1)
    print("\r" + " " * 25, end='\r', flush=True)  # Очистка строки после остановки

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
        """Сканирует папку и подпапки с отображением хода работы и анимацией."""
        check_path = self.shared_folder_path.replace('/', '\\')

        if not os.path.exists(check_path):
            error_msg = f"{Fore.RED}Ошибка: Путь {check_path} не существует или недоступен."
            print(error_msg)
            self.errors.append(error_msg)
            return

        print(f"{Fore.GREEN}🔍 Начинаем сканирование папки: {check_path}")

        # Флаг для управления анимацией
        anim_active = [True]
        anim_thread = threading.Thread(target=animate_scanning, args=(anim_active,))
        anim_thread.start()

        try:
            for root, dirs, files in os.walk(check_path):
                for file in files:
                    # Выводим, что именно проверяем
                    print(f"\r{Fore.YELLOW}🔎 Проверяю файл: {os.path.join(root, file)}", end='', flush=True)
                    try:
                        self._check_file(root, file)
                    except Exception as e:
                        error_msg = f"{Fore.RED}⚠️ Ошибка при обработке файла '{file}' в директории '{root}': {e}"
                        print("\n" + error_msg)
                        self.errors.append(error_msg)
                # После каждой папки очищаем строку с именем файла
                print("\r" + " " * 60, end='\r', flush=True)
        except Exception as e:
            error_msg = f"{Fore.RED}❗ Критическая ошибка при сканировании: {e}"
            print("\n" + error_msg)
            self.errors.append(error_msg)
        finally:
            anim_active[0] = False
            anim_thread.join()
            print("\rСканирование завершено. " + " " * 40)  # Очистка строки

    def _get_file_owner(self, full_path):
        """Получает владельца файла. В Windows возвращает имя текущего пользователя."""
        try:
            return getpass.getuser()
        except Exception:
            return "Неизвестно"

    def _get_file_icon(self, filename):
        """Возвращает иконку для файла на основе расширения."""
        ext = Path(filename).suffix.lower()
        return self.FILE_ICONS.get(ext, '📁')

    def _check_file(self, folder_path, filename):
        """Проверяет файл на соответствие ключевым словам."""
        filename_lower = filename.lower()

        for term in self.SEARCH_TERMS:
            if term in filename_lower:
                full_path = os.path.join(folder_path, filename)
                try:
                    file_size = os.path.getsize(full_path)
                    last_modified = datetime.fromtimestamp(os.path.getmtime(full_path))
                    created_time = datetime.fromtimestamp(os.path.getctime(full_path))

                    owner = self._get_file_owner(full_path)
                    last_editor = "Неизвестно (требуется pywin32)"
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
                    error_msg = f"{Fore.RED}❌ Ошибка доступа к файлу '{full_path}': {e}"
                    print("\n" + error_msg)
                    self.errors.append(error_msg)

    def _generate_report(self):
        """Выводит отчёт о найденных файлах в консоль."""
        print(f"\n{Fore.MAGENTA}{'='*80}")
        print("🔍 ОТЧЁТ О РЕЗУЛЬТАТАХ АУДИТА")
        print(f"{'='*80}{Style.RESET_ALL}")

        if self.errors:
            print(f"{Fore.RED}⚠️  ОБНАРУЖЕНЫ ОШИБКИ В ПРОЦЕССЕ СКАНИРОВАНИЯ:")
            for i, error in enumerate(self.errors, 1):
                print(f"{i}. {error}")
            print()

        is_folder_empty = len(self.results) == 0 and len(self.errors) == 0

        if is_folder_empty:
            print(f"{Fore.BLUE}ℹ️  Папка пуста или не содержит файлов для проверки.")
            return

        if not self.results and self.errors:
            print(f"{Fore.RED}❌ Файлы с чувствительными данными не обнаружены.")
            return

        print(f"{Fore.GREEN}✅ Найдено файлов: {len(self.results)}")
        print("-"*80)

        sorted_results = sorted(self.results, key=lambda x: x['last_modified'], reverse=True)

        for i, item in enumerate(sorted_results, 1):
            print(f"{i}. {item['icon']} Файл: {item['filename']}")
            print(f"   📂 Путь: {item['path']}")
            print(f"   💾 Размер: {item['size_kb']} KB")
            print(f"   🗓️  Создан: {item['created'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   ⏱️  Последнее изменение: {item['last_modified'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   👤 Владелец: {item['owner']}")
            print(f"   ✍️  Последний редактор: {item['last_editor']}")
            print(f"   🔍 Найдено по ключевому слову: '{item['keyword_found']}'\n")

    def save_to_txt(self):
        """Сохраняет отчёт в TXT-файл в той же папке, где находится скрипт."""
        script_dir = Path(__file__).parent
        report_filename = script_dir / "audit_report.txt"

        if len(self.results) == 0 and len(self.errors) == 0:
            print(f"{Fore.RED}❌ Нет данных для сохранения (папка пуста, ошибок нет).")
            return

        try:
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write("🔍 ОТЧЁТ О РЕЗУЛЬТАТАХ АУДИТА\n")
                f.write("="*80 + "\n\n")

                f.write(f"Путь к папке: {self.shared_folder_path}\n")
                f.write(f"Пользователь: {getpass.getuser()}\n")
                f.write(f"Дата и время генерации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                if self.errors:
                    f.write("⚠️  ОБНАРУЖЕНЫ ОШИБКИ В ПРОЦЕССЕ СКАНИРОВАНИЯ:\n")
                    for error in self.errors:
                        f.write(f"- {error}\n")
                    f.write("\n")

                if len(self.results) == 0 and self.errors:
                    f.write("❌ Файлы с чувствительными данными не обнаружены.\n")
                elif len(self.results) > 0:
                    f.write(f"✅ Найдено файлов: {len(self.results)}\n")
                    f.write("-"*80 + "\n")

                    sorted_results = sorted(self.results, key=lambda x: x['last_modified'], reverse=True)

                    for item in sorted_results:
                        f.write(f"{item['icon']} Файл: {item['filename']}\n")
                        f.write(f"📂 Путь: {item['path']}\n")
                        f.write(f"💾 Размер: {item['size_kb']} KB\n")
                        f.write(f"🗓️  Создан: {item['created'].strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"⏱️  Последнее изменение: {item['last_modified'].strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"👤 Владелец: {item['owner']}\n")
                        f.write(f"✍️  Последний редактор: {item['last_editor']}\n")
                        f.write(f"🔍 Найдено по ключевому слову: '{item['keyword_found']}'\n\n")

                f.write("="*80 + "\n")
                f.write("🛡️ Конец отчёта\n")

            print(f"{Fore.GREEN}✅ Отчёт успешно сохранён в файл: {report_filename}")

        except Exception as e:
            print(f"{Fore.RED}❌ Ошибка при сохранении отчёта: {e}")

def show_description():
    """Выводит краткое описание программы."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print("="*50)
    print("🛡️ FileAuditor v1.4 - Краткое описание")
    print("="*50)
    print("Программа FileAuditor предназначена для автоматического аудита файлов в указанной папке.")
    print("Она ищет файлы, в именах которых содержатся ключевые слова, связанные с персональными данными:")
    print("- паспорт, СНИЛС, ИНН, ФИО и др.")
    print("\nФункции:")
    print("- Сканирование папок и подпапок.")
    print("- Поиск по ключевым словам.")
    print("- Отображение владельца файла и времени изменения.")
    print("- Сохранение отчёта в текстовый файл (audit_report.txt).")
    print("- Красивый цветной вывод и анимация сканирования.")
    input("\nНажмите Enter для возврата в меню...")

def main():
    """
    Основная функция с меню для взаимодействия с пользователем.
    """
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("="*45)
        print("🛡️ FileAuditor v1.4 - Главное меню")
        print("="*45)
        
        print("[1] Запустить аудит папки")
        print("[2] О программе (описание)")
        print("[3] Выход")
        
        choice = input("Выберите действие (1/2/3): ").strip()
        
        if choice == '1':
            folder_path = input("\nВведите полный путь к папке для аудита (или 'выход' для возврата): ").strip()
            
            if folder_path.lower() == 'выход':
                continue

            auditor = FileAuditor(folder_path)
            
            auditor.scan_folder()
            auditor._generate_report()
            auditor.save_to_txt()
            
            input("\nНажмите Enter для возврата в меню...")
        
        elif choice == '2':
            show_description()
        
        elif choice == '3':  # <-- Ошибка была здесь (отступ не совпадал с 'if')
            print("До свидания! Спасибо за использование.")
            break

if __name__ == "__main__":
    main()