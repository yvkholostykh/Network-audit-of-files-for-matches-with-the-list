import os
import sys
import getpass
import time
import threading
from datetime import datetime
from pathlib import Path

# --- Анимация загрузки ---
def animate_scanning(active_flag):
    """Запускает анимацию загрузки, пока флаг active_flag[0] == True."""
    for c in r'-\|/-\|/':
        if not active_flag[0]:
            break
        print(f"\r🔍 Сканирование: {c}", end='', flush=True)
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
            error_msg = f"Ошибка: Путь {check_path} не существует или недоступен."
            print(error_msg)
            self.errors.append(error_msg)
            return

        print(f"🔍 Начинаем сканирование папки: {check_path}")

        # Флаг для управления анимацией
        anim_active = [True]
        anim_thread = threading.Thread(target=animate_scanning, args=(anim_active,))
        anim_thread.start()

        try:
            for root, dirs, files in os.walk(check_path):
                for file in files:
                    # Выводим, что именно проверяем
                    print(f"\r🔎 Проверяю файл: {os.path.join(root, file)}", end='', flush=True)
                    try:
                        self._check_file(root, file)
                    except Exception as e:
                        error_msg = f"⚠️ Ошибка при обработке файла '{file}' в директории '{root}': {e}"
                        print("\n" + error_msg)
                        self.errors.append(error_msg)
                # После каждой папки очищаем строку с именем файла
                print("\r" + " " * 60, end='\r', flush=True)
        except Exception as e:
            error_msg = f"❗ Критическая ошибка при сканировании: {e}"
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
                    error_msg = f"❌ Ошибка доступа к файлу '{full_path}': {e}"
                    print("\n" + error_msg)
                    self.errors.append(error_msg)

    def _generate_report(self):
        """Выводит отчёт о найденных файлах в консоль."""
        print("\n" + "="*80)
        print("🔍 ОТЧЁТ О РЕЗУЛЬТАТАХ АУДИТА")
        print("="*80)

        if self.errors:
            print("⚠️  ОБНАРУЖЕНЫ ОШИБКИ В ПРОЦЕССЕ СКАНИРОВАНИЯ:")
            for i, error in enumerate(self.errors, 1):
                print(f"{i}. {error}")
            print()

        is_folder_empty = len(self.results) == 0 and len(self.errors) == 0

        if is_folder_empty:
            print("ℹ️  Папка пуста или не содержит файлов для проверки.")
            return

        if not self.results and self.errors:
            print("❌ Файлы с чувствительными данными не обнаружены.")
            return

        print(f"✅ Найдено файлов: {len(self.results)}")
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
            print("❌ Нет данных для сохранения (папка пуста, ошибок нет).")
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

            print(f"✅ Отчёт успешно сохранён в файл: {report_filename}")

        except Exception as e:
            print(f"❌ Ошибка при сохранении отчёта: {e}")

def main():
    """
    Основная функция для взаимодействия с пользователем.
    """
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')  # Очистка консоли
        print("="*45)
        print("🛡️ FileAuditor v1.3 - Аудит файлов")
        print("="*45)
        
        folder_path = input("Введите полный путь к папке для аудита (или 'выход' для завершения): ").strip()

        if folder_path.lower() == 'выход':
            print("До свидания! Спасибо за использование.")
            break

        auditor = FileAuditor(folder_path)
        
        # Сканирование с анимацией и выводом хода работы
        auditor.scan_folder()
        
        # Всегда формируем и выводим отчёт, даже если нет результатов
        auditor._generate_report()
        
        # Сохраняем отчёт в TXT (всегда в папку со скриптом)
        auditor.save_to_txt()
        
        input("Нажмите Enter для продолжения...")

if __name__ == "__main__":
    main()