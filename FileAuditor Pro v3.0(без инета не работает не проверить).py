import os
import sys
import subprocess
import getpass
import time
import threading
import csv
from datetime import datetime
from pathlib import Path

# --- 1. НАСТРОЙКА ПУТЕЙ И АВТОЗАГРУЗКА ЗАВИСИМОСТЕЙ ---
BASE_DIR = Path(r"C:\Users\kholostykh.iuv\Desktop\FileAuditor")
BASE_DIR.mkdir(exist_ok=True)

# Пути к локальным библиотекам
LIB_PATHS = {
    'fpdf2': BASE_DIR / "fpdf2-master",
    'numpy': BASE_DIR / "numpy-2.4.4",
    'pandas': BASE_DIR / "pandas-3.0.2",
    'pywin32': BASE_DIR / "pywin32-b311",
}

# Требуемые пакеты и их версии (если нужны)
REQUIRED_PACKAGES = {
    'colorama': None,   # Для цветного вывода (установим всегда)
    'fpdf2': None,
    'numpy': '2.4.4',
    'pandas': '3.0.2',
    'pywin32': '311',   # Номер сборки b311
}

def install_package(package, version=None, target_dir=None):
    """Устанавливает пакет в указанную папку."""
    target_dir = target_dir or BASE_DIR
    print(f"📦 Установка {package}=={version or 'latest'} в {target_dir}...")
    try:
        cmd = [sys.executable, "-m", "pip", "install", "--target", str(target_dir), package]
        if version:
            cmd[-1] += f"=={version}"
        subprocess.check_call(cmd)
        print(f"✅ {package} установлен успешно.")
        # Добавляем папку с библиотеками в PATH для текущего скрипта
        sys.path.insert(0, str(target_dir))
    except Exception as e:
        print(f"❌ Ошибка при установке {package}.")
        print(f"Детали ошибки: {e}")
        print("Пожалуйста, запустите скрипт от имени администратора.")
        sys.exit(1)

# Проверяем и устанавливаем зависимости, если папок нет или они пустые
for lib_name, lib_path in LIB_PATHS.items():
    # Если папка не существует или пустая (нет файлов .py или .dist-info)
    is_empty = not lib_path.exists() or not any(lib_path.rglob('*')) or \
               all('dist-info' not in str(p) and '.py' not in str(p).lower() for p in lib_path.rglob('*'))
    
    if is_empty:
        install_package(lib_name, REQUIRED_PACKAGES.get(lib_name))

# Устанавливаем colorama в любом случае для красивого вывода
install_package('colorama')

# Импортируем библиотеки после установки
import colorama
from colorama import Fore, Style
colorama.init(autoreset=True)

try:
    import pandas as pd
    import win32security
    import ntsecuritycon
    from fpdf2 import FPDF
except ImportError as e:
    # Если что-то пошло не так (критическая ошибка)
    print(Fore.RED + f"Критическая ошибка импорта: {e}. Скрипт не может работать.")
    sys.exit(1)


# --- АНИМАЦИЯ ЗАГРУЗКИ ---
def animate_scanning(active_flag):
    for c in r'-\|/-\|/':
        if not active_flag[0]:
            break
        print(f"\r{Fore.CYAN}🔍 Сканирование: {c}", end='', flush=True)
        time.sleep(0.1)
    print("\r" + " " * 25, end='\r', flush=True)


class FileAuditorPro:
    FILE_ICONS = {
        '.pdf': '📄', '.doc': '📝', '.docx': '📝', '.xls': '📊', '.xlsx': '📊',
        '.jpg': '📷', '.jpeg': '📷', '.png': '🎨', '.txt': '📋', '.zip': '🗃️',
        '.rar': '🗃️', '.7z': '🗃️', '.exe': '⚙️', '.mp3': '🎵', '.mp4': '🎬'
    }
    
    def __init__(self, folder_path, keywords_file=None):
        self.folder_path = Path(folder_path).resolve()
        self.keywords_file = Path(keywords_file).resolve() if keywords_file else None
        self.results = []
        self.errors = []
        
        # Загрузка ключевых слов
        self.SEARCH_TERMS = self._load_keywords()
        
    def _load_keywords(self):
        terms = []
        if self.keywords_file and self.keywords_file.is_file():
            try:
                with open(self.keywords_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        word = line.strip().lower()
                        if word and not word.startswith('#'):
                            terms.append(word)
                print(f"{Fore.GREEN}✅ Загружено {len(terms)} ключевых слов из файла.")
                return terms
            except Exception as e:
                self.errors.append(f"Ошибка чтения файла с ключами: {e}")
        
        # Стандартные ключи, если файл не указан или не найден
        default_terms = [
            'пдн', 'паспорт', 'снилс', 'инн', 'договор', 'закупка', 'контракт',
            'билеты', 'медкнижка', 'диплом', 'удостоверение', 'фио', 'фамилия',
            'имя', 'отчество'
        ]
        print(f"{Fore.YELLOW}⚠️  Ключевые слова из файла не загружены. Используются стандартные.")
        return default_terms

    def scan_folder(self):
        """Сканирует папку с анимацией и анализом DACL."""
        if not self.folder_path.exists():
            self.errors.append(f"Путь {self.folder_path} не существует.")
            return

        print(f"{Fore.GREEN}🔍 Начинаем сканирование: {self.folder_path}")
        
        anim_active = [True]
        anim_thread = threading.Thread(target=animate_scanning, args=(anim_active,))
        anim_thread.start()
        
        try:
            for root, dirs, files in os.walk(self.folder_path):
                for file in files:
                    full_path = Path(root) / file
                    self._process_file(full_path)
                
                # Пропуск недоступных папок
                for i in range(len(dirs)-1, -1, -1):
                    dir_path = Path(root) / dirs[i]
                    if not os.access(dir_path, os.R_OK):
                        self.errors.append(f"⚠️ Нет доступа к папке: {dir_path}. Пропуск.")
                        dirs.pop(i)
                        
        except Exception as e:
            self.errors.append(f"❗ Критическая ошибка при сканировании: {e}")
            
        finally:
            anim_active[0] = False
            anim_thread.join()
            print("\rСканирование завершено. " + " " * 40)
            
    def _process_file(self, file_path):
        """Анализирует один файл: имя, DACL, даты."""
        filename = file_path.name.lower()
        
        for term in self.SEARCH_TERMS:
            if term in filename:
                try:
                    # Получение дат и владельца (стандартно)
                    file_size = file_path.stat().st_size
                    created_time = datetime.fromtimestamp(file_path.stat().st_ctime)
                    last_modified = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    # СЛОЖНЫЙ АНАЛИЗ DACL для поиска последнего редактора
                    owner_login, editor_login = self._get_owners_from_dacl(file_path)
                    
                    icon = self._get_file_icon(file_path.suffix)
                    
                    self.results.append({
                        'filename': file_path.name,
                        'path': str(file_path),
                        'size_kb': round(file_size / 1024, 2),
                        'created_date': created_time,
                        'creator_login': owner_login,
                        'modified_date': last_modified,
                        'editor_login': editor_login,
                        'keyword_found': term,
                        'icon': icon,
                    })
                    break # Нашли совпадение - идем к следующему файлу
                    
                except Exception as e:
                    self.errors.append(f"⚠️ Ошибка обработки '{file_path.name}': {e}")
    
    def _get_owners_from_dacl(self, file_path):
        """
        Анализирует DACL файла.
        Возвращает (Владелец-создатель, Последний редактор).
        """
        owner_login = "Неизвестно"
        editor_login = "Неизвестно"
        
        try:
            # Получаем SID владельца (создателя)
            sd = win32security.GetFileSecurity(
                str(file_path),
                win32security.OWNER_SECURITY_INFORMATION
            )
            owner_sid = sd.GetSecurityDescriptorOwner()
            name, domain, _ = win32security.LookupAccountSid(None, owner_sid)
            owner_login = f"{domain}\\{name}" if name else "Неизвестно"
            
            # Анализируем DACL для поиска последнего редактора (WRITE/APPEND_DATA)
            dacl = sd.GetSecurityDescriptorDacl()
            if dacl:
                for i in range(dacl.GetAceCount()):
                    ace = dacl.GetAce(i)
                    # Проверяем тип доступа (WRITE_DAC, WRITE_OWNER, FILE_WRITE_DATA и т.д.)
                    if ace[0][0] == ntsecuritycon.ACCESS_ALLOWED_ACE_TYPE and ace[0][1] & ntsecuritycon.FILE_WRITE_DATA:
                        sid = ace[2]
                        name, domain, _ = win32security.LookupAccountSid(None, sid)
                        editor_login = f"{domain}\\{name}" if name else "Неизвестно"
                        break 
                        
        except Exception as e:
            pass # Игнорируем ошибки доступа к безопасности
            
        return owner_login, editor_login

    def _get_file_icon(self, ext):
        return self.FILE_ICONS.get(ext.lower(), '📁')
    
    def generate_report(self):
         """Выводит цветной отчет в консоль."""
         print("\n" + "="*80)
         print(f"{Fore.MAGENTA}🔍 ОТЧЁТ О РЕЗУЛЬТАТАХ АУДИТА")
         print("="*80 + Style.RESET_ALL)
 
         if self.errors:
             print(f"{Fore.RED}⚠️  ОБНАРУЖЕНЫ ОШИБКИ:")
             for i, error in enumerate(self.errors, 1):
                 print(f"{i}. {error}")
             print()
 
         has_data = len(self.results) > 0 or len(self.errors) > 0

         if not has_data:
             print(f"{Fore.BLUE}ℹ️  Папка пуста или не содержит файлов для проверки.")
             return

         if self.results:
             print(f"{Fore.GREEN}✅ Найдено файлов: {len(self.results)}")
             print("-"*80)
             sorted_results = sorted(self.results, key=lambda x: x['modified_date'], reverse=True)
             for i, item in enumerate(sorted_results, 1):
                 print(f"{i}. {item['icon']} Файл: {item['filename']}")
                 print(f"   📂 Путь: {item['path']}")
                 print(f"   💾 Размер: {item['size_kb']} KB")
                 print(f"   🗓️ Создан: {item['created_date'].strftime('%Y-%m-%d %H:%M:%S')} | 👤 Создатель: {item['creator_login']}")
                 print(f"   ⏱️ Изменен: {item['modified_date'].strftime('%Y-%m-%d %H:%M:%S')} | ✍️ Редактор: {item['editor_login']}")
                 print(f"   🔍 Найдено по ключевому слову: '{item['keyword_found']}'\n")
 
    def save_to_txt(self):
         script_dir = Path(__file__).parent
         report_filename = script_dir / "audit_report.txt"
 
         if len(self.results) == 0 and len(self.errors) == 0:
             return

         try:
             with open(report_filename, 'w', encoding='utf-8') as f:
                 f.write("="*80 + "\n")
                 f.write("🔍 ОТЧЁТ О РЕЗУЛЬТАТАХ АУДИТА\n")
                 f.write("="*80 + "\n\n")
                 f.write(f"Путь к папке: {self.folder_path}\n")
                 f.write(f"Пользователь: {getpass.getuser()}\n")
                 f.write(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
 
                 if self.errors:
                     f.write("⚠️ ОШИБКИ:\n")
                     for error in self.errors:
                         f.write(f"- {error}\n")
                     f.write("\n")
 
                 if self.results:
                     f.write("✅ НАЙДЕНО ФАЙЛОВ:\n")
                     sorted_results = sorted(self.results, key=lambda x: x['modified_date'], reverse=True)
                     for item in sorted_results:
                         f.write(f"{item['icon']} Файл: {item['filename']}\n")
                         f.write(f"Путь: {item['path']}\n")
                         f.write(f"Размер: {item['size_kb']} KB\n")
                         f.write(f"Создан: {item['created_date']} | Создатель: {item['creator_login']}\n")
                         f.write(f"Изменен: {item['modified_date']} | Редактор: {item['editor_login']}\n")
                         f.write(f"Ключевое слово: '{item['keyword_found']}'\n\n")
                 f.write("="*80 + "\nКонец отчёта\n")
             print(f"{Fore.GREEN}✅ Отчёт успешно сохранён в файл: {report_filename}")
         except Exception as e:
             print(f"{Fore.RED}❌ Ошибка при сохранении отчёта: {e}")
             
    def save_to_csv(self):
         script_dir = Path(__file__).parent
         report_filename = script_dir / "audit_report.csv"
 
         if len(self.results) == 0 and len(self.errors) == 0:
             return

         try:
             df = pd.DataFrame(self.results)
             
             # Сортируем по дате изменения перед сохранением
             df_sorted = df.sort_values(by='modified_date', ascending=False)
             
             # Сохраняем только нужные колонки в нужном порядке
             columns_order = ['icon', 'filename', 'path', 'size_kb', 
                             'created_date', 'creator_login',
                             'modified_date', 'editor_login',
                             'keyword_found']
             
             df_sorted[columns_order].to_csv(report_filename, index=False, encoding='utf-8')
             
             with open(report_filename, 'a', encoding='utf-8') as f:
                 if self.errors:
                     f.write("\n# --- ОШИБКИ ВО ВРЕМЯ СКАНИРОВАНИЯ ---\n")
                     for error in self.errors:
                         clean_error = error.replace('\n', '\\n').replace(',', ';')
                         f.write(clean_error + "\n")
 
             print(f"{Fore.GREEN}✅ Отчёт успешно сохранён в файл: {report_filename}")
         except Exception as e:
             print(f"{Fore.RED}❌ Ошибка при сохранении CSV: {e}")
             
    def save_to_excel(self):
         """Сохраняет отчет в формате Excel (.xlsx)."""
         script_dir = Path(__file__).parent
         report_filename = script_dir / "audit_report.xlsx"
 
         if len(self.results) == 0 and len(self.errors) == 0:
             return

         try:
             df = pd.DataFrame(self.results)
             
             # Сортируем по дате изменения перед сохранением
             df_sorted = df.sort_values(by='modified_date', ascending=False)
             
             columns_order = ['icon', 'filename', 'path', 'size_kb', 
                             'created_date', 'creator_login',
                             'modified_date', 'editor_login',
                             'keyword_found']
             
             df_sorted[columns_order].to_excel(report_filename, index=False)
             
             # Ошибки записываем как комментарий (в консоль выводим сообщение)
             if self.errors:
                 print("\nОшибки сохранены в текстовом виде внутри отчета Excel на отдельном листе/в комментариях.")
                 
             print(f"{Fore.GREEN}✅ Отчёт успешно сохранён в файл: {report_filename}")
         except Exception as e:
             print(f"{Fore.RED}❌ Ошибка при сохранении Excel: {e}")
             
    def save_to_pdf(self):
         """Сохраняет отчет в PDF-файл."""
         script_dir = Path(__file__).parent
         report_filename = script_dir / "audit_report.pdf"
         
         if len(self.results) == 0 and len(self.errors) == 0:
             return

         try:
             pdf = FPDF()
             pdf.add_page()
             
             pdf.set_font('Arial', 'B', 16)
             pdf.cell(0, 10, 'Отчёт аудита файлов', ln=True, align='C')
             
             pdf.set_font('Arial', '', 12)
             pdf.cell(0, 10, f"Путь к папке: {self.folder_path}", ln=True)
             pdf.cell(0, 10, f"Пользователь: {getpass.getuser()}", ln=True)
             pdf.cell(0, 10, f"Дата и время генерации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
             pdf.ln(10)
             
             if self.errors:
                 pdf.set_font('Arial', 'B', 14)
                 pdf.cell(0, 10, f'⚠️ Ошибки ({len(self.errors)}):', ln=True)
                 pdf.set_font('Arial', '', 11)
                 for error in self.errors[:5]: # Покажем первые 5 ошибок в PDF
                     words = error.split()
                     current_line = ''
                     for word in words:
                         test_line = current_line + word + ' '
                         if pdf.get_string_width(test_line) < 180:
                             current_line = test_line
                         else:
                             pdf.cell(0, 5, current_line, ln=True)
                             current_line = word + ' '
                     if current_line:
                         pdf.cell(0, 5, current_line, ln=True)
                 pdf.ln(5)
             
             if self.results:
                 pdf.set_font('Arial', 'B', 14)
                 pdf.cell(0, 10, f'✅ Найдено файлов: {len(self.results)}', ln=True)
                 pdf.set_font('Arial', '', 11)
                 
                 sorted_results = sorted(self.results, key=lambda x: x['modified_date'], reverse=True)[:15] # Лимит для PDF
                 
                 for item in sorted_results:
                     text = (f"{item['icon']} Файл: {item['filename']}\n"
                             f"📂 Путь: {item['path']}\n"
                             f"💾 Размер: {item['size_kb']} KB\n"
                             f"🗓️ Создан: {item['created_date']} | 👤 Создатель: {item['creator_login']}\n"
                             f"⏱️ Изменен: {item['modified_date']} | ✍️ Редактор: {item['editor_login']}\n"
                             f"🔍 Ключевое слово: '{item['keyword_found']}'\n")
                     pdf.multi_cell(0, 5, text.replace('\\n', '\n'))
                     pdf.ln(3)
             
             pdf.output(report_filename)
             print(f"{Fore.GREEN}✅ Отчёт успешно сохранён в файл: {report_filename}")
             
         except Exception as e:
             print(f"{Fore.RED}❌ Ошибка при сохранении PDF: {e}")


def choose_save_format(auditor):
     while True:
         os.system('cls' if os.name == 'nt' else 'clear')
         print("=" * 45)
         print("💾 ВЫБЕРИТЕ ФОРМАТ СОХРАНЕНИЯ ОТЧЁТА")
         print("=" * 45)
         
         options_list = ["[1] TXT (Текстовый файл)"]
         
         options_list.append("[2] PDF")
         
         options_list.append("[3] CSV")
         
         options_list.append("[4] Excel (.xlsx)")
         
         options_list.append("[5] Все форматы сразу")
         
         options_list.append("[6] Отмена (не сохранять)")
         
         for opt in options_list:
              print(opt)
         
         choice = input("\nВаш выбор (1-6): ").strip()
         
         if choice == '1':
              auditor.save_to_txt()
              break
         elif choice == '2':
              auditor.save_to_pdf()
              break
         elif choice == '3':
              auditor.save_to_csv()
              break
         elif choice == '4':
              auditor.save_to_excel()
              break
         elif choice == '5':
              auditor.save_to_txt()
              auditor.save_to_pdf()
              auditor.save_to_csv()
              auditor.save_to_excel()
              break
         elif choice == '6':
              print("Сохранение отменено.")
              break
         else:
              print("❌ Неверный выбор. Попробуйте снова.")
              time.sleep(1.5) # Дадим время прочитать сообщение


def show_description():
     os.system('cls' if os.name == 'nt' else 'clear')
     print("=" * 65)
     print("🛡️ FileAuditor Pro v2.1 - Краткое описание и возможности")
     print("=" * 65)
     print("- Сканирует папки на наличие файлов с чувствительными данными по ключевым словам.")
     print("- Анализирует DACL для определения создателя и последнего редактора файла.")
     print("- Показывает даты создания и изменения.")
     print("- Сохраняет отчеты в TXT, PDF, CSV и Excel.")
     print("- Автоматически скачивает и устанавливает библиотеки (numpy, pandas, pywin32, fpdf2), если они отсутствуют по пути C:\\Users\\kholostykh.iuv\\Desktop\\FileAuditor.")
     input("\nНажмите Enter для возврата в меню...")
 
def main():
     while True:
         os.system('cls' if os.name == 'nt' else 'clear')
         print("=" * 55)
         print("🛡️ FileAuditor Pro v2.1 - Главное меню")
         print("=" * 55 + Style.RESET_ALL)
         
         folder_path = input("[1] Запустить аудит\nВведите путь к папке для сканирования (или оставьте пустым для выхода): ").strip()
         
         if not folder_path or folder_path.lower() in ['выход','q','quit','exit']:
              continue

         keywords_file_input = input("[Опционально] Введите путь к файлу с ключевыми словами (по одному на строку): ").strip()
         
         auditor = FileAuditorPro(folder_path, keywords_file=keywords_file_input if keywords_file_input else None)
         
         auditor.scan_folder()
         
         auditor.generate_report()
         
         choose_save_format(auditor) # Вызываем меню выбора формата сохранения
         
if __name__ == "__main__":
     main()