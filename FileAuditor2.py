import os
import sys
import subprocess
import getpass
from datetime import datetime
from pathlib import Path

# --- 1. АВТОМАТИЧЕСКАЯ УСТАНОВКА ЗАВИСИМОСТЕЙ ---
required_packages = ['fpdf2']
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
            print("Пожалуйста, установите пакет вручную: pip install fpdf2")
            sys.exit(1)

from fpdf2 import FPDF

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
        """Сканирует папку и подпапки на наличие файлов с ключевыми словами."""
        check_path = self.shared_folder_path.replace('/', '\\')

        if not os.path.exists(check_path):
            error_msg = f"Ошибка: Путь {check_path} не существует или недоступен."
            print(error_msg)
            self.errors.append(error_msg)
            return

        print(f"🔍 Начинаем сканирование папки: {check_path}")

        try:
            for root, dirs, files in os.walk(check_path):
                for file in files:
                    try:
                        self._check_file(root, file)
                    except Exception as e:
                        error_msg = f"⚠️ Ошибка при обработке файла '{file}' в директории '{root}': {e}"
                        print(error_msg)
                        self.errors.append(error_msg)
        except Exception as e:
            error_msg = f"❗ Критическая ошибка при сканировании: {e}"
            print(error_msg)
            self.errors.append(error_msg)

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
                    print(error_msg)
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

        # Проверка на пустую папку (нет файлов и нет ошибок доступа)
        is_folder_empty = len(self.results) == 0 and len(self.errors) == 0

        if is_folder_empty:
            print("ℹ️  Папка пуста или не содержит файлов для проверки.")
            return

        if not self.results and self.errors:
            print("❌ Файлы с чувствительными данными не обнаружены.")
            return

        print(f"✅ Найдено файлов: {len(self.results)}")
        print("-"*80)

        # Сортируем по дате изменения (новые первыми)
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

    def save_to_pdf(self, pdf_path='audit_report.pdf'):
        """Сохраняет отчёт в PDF-файл."""

        # Проверяем, есть ли что сохранять (результаты или ошибки)
        if len(self.results) == 0 and len(self.errors) == 0:
            print("❌ Нет данных для сохранения в PDF (папка пуста).")
            return

        pdf = FPDF()
        pdf.add_page()

        # Заголовок и информация о системе
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'Отчёт аудита файлов', ln=True, align='C')

        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, f"Путь к папке: {self.shared_folder_path}", ln=True)
        pdf.cell(0, 10, f"Пользователь: {getpass.getuser()}", ln=True)
        pdf.cell(0, 10, f"Дата и время генерации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
        pdf.ln(10)

        # Ошибки
        if self.errors:
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, '⚠️ Ошибки:', ln=True)
            pdf.set_font('Arial', '', 11)
            for error in self.errors:
                words = error.split()
                current_line = ''
                for word in words:
                    if len(current_line + word) < 95:
                        current_line += word + ' '
                    else:
                        pdf.cell(0, 5, current_line, ln=True)
                        current_line = word + ' '
                if current_line:
                    pdf.cell(0, 5, current_line, ln=True)
            pdf.ln(10)

        # Результаты поиска
        if self.results:
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, f'✅ Найдено файлов: {len(self.results)}', ln=True)
            pdf.set_font('Arial', '', 11)
            for item in self.results:
                pdf.multi_cell(0, 5, f"{item['icon']} Файл: {item['filename']}\n"
                                       f"📂 Путь: {item['path']}\n"
                                       f"💾 Размер: {item['size_kb']} KB\n"
                                       f"🗓️  Создан: {item['created'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                                       f"⏱️  Последнее изменение: {item['last_modified'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                                       f"👤 Владелец: {item['owner']}\n"
                                       f"✍️  Последний редактор: {item['last_editor']}\n"
                                       f"🔍 Найдено по ключевому слову: '{item['keyword_found']}'\n")
                pdf.ln(5)

        try:
            pdf.output(pdf_path)
            print(f"✅ Отчёт успешно сохранён в файл: {pdf_path}")
        except Exception as e:
            print(f"❌ Ошибка при сохранении PDF: {e}")

def main():
    """
    Основная функция для взаимодействия с пользователем.
    """
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')  # Очистка консоли
        print("="*45)
        print("🛡️ FileAuditor v1.2 - Аудит файлов")
        print("="*45)
        folder_path = input("Введите полный путь к папке для аудита (или 'выход' для завершения): ").strip()

        if folder_path.lower() == 'выход':
            print("До свидания! Спасибо за использование.")
            break

        auditor = FileAuditor(folder_path)
        auditor.scan_folder()
        auditor._generate_report()
        save_choice = input("Хотите сохранить отчёт в PDF? (да/нет): ").strip().lower()

        if save_choice in ['да', 'д', 'yes', 'y']:
            pdf_filename = input("Введите имя файла для сохранения (например, report.pdf): ").strip()
            if not pdf_filename.endswith('.pdf'):
                pdf_filename += '.pdf'
            auditor.save_to_pdf(pdf_filename)

        input("Нажмите Enter для продолжения...")

if __name__ == "__main__":
    main()