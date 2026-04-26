import os
import sys
import getpass
import time
import threading
import csv
from datetime import datetime
from pathlib import Path

# --- 1. ПОДКЛЮЧЕНИЕ ЛОКАЛЬНЫХ БИБЛИОТЕК ПО УКАЗАННЫМ ПУТЯМ ---
BASE_DIR = Path(r"C:\Users\kholostykh.iuv\Desktop\FileAuditor")

# Пути к вашим библиотекам
LIB_PATHS = {
    'colorama': BASE_DIR / "colorama-master",
    'fpdf2': BASE_DIR / "fpdf2-master",
    'numpy': BASE_DIR / "numpy-2.4.4",
    'pandas': BASE_DIR / "pandas-3.0.2",
    'pywin32': BASE_DIR / "pywin32-b311",
}

# Добавляем пути к библиотекам в начало sys.path
for path in LIB_PATHS.values():
    if path.exists() and path.is_dir():
        sys.path.insert(0, str(path))

# --- 2. ПОПЫТКА ИМПОРТА БИБЛИОТЕК С ЛОКАЛЬНЫХ ПУТЕЙ ---
fpdf2_available = False
pandas_available = False
pywin32_available = False

try:
    import colorama
    from colorama import Fore, Style
    colorama.init(autoreset=True)
except ImportError:
    class ColorFallback:
        GREEN = ""
        RED = ""
        CYAN = ""
        MAGENTA = ""
        BLUE = ""
        YELLOW = ""
        RESET_ALL = ""
    Fore = ColorFallback()
    Style = ColorFallback()


try:
    from fpdf2 import FPDF
    fpdf2_available = True
except ImportError:
    print("⚠️  Библиотека fpdf2 не найдена по пути. Сохранение в PDF будет недоступно.")

try:
    import pandas as pd
    pandas_available = True
except ImportError:
    print("⚠️  Библиотека pandas не найдена по пути. Сохранение в CSV/Excel будет недоступно.")

try:
    import win32security
    import ntsecuritycon
    pywin32_available = True
except ImportError:
    print("⚠️  Библиотека pywin32 не найдена по пути. Анализ владельцев файлов будет недоступен.")


# --- АНИМАЦИЯ И ПРОГРЕСС СКАНИРОВАНИЯ ---
def scan_progress(total_files, processed_files):
    """Тред для вывода интерактивного прогресса."""
    while True:
        if total_files[0] == 0 or processed_files[0] > total_files[0]:
            print(f"\r", end='', flush=True)
            break

        percent = (processed_files[0] / total_files[0]) * 100
        status_line = f"\r{Fore.CYAN}📊 Сканирование: {percent:.1f}% | Проверено: {processed_files[0]}/{total_files[0]} файлов"
        print(status_line, end='', flush=True)
        time.sleep(0.2) 

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
        
        default_terms = [
            'пдн', 'паспорт', 'снилс', 'инн', 'договор', 'закупка', 'контракт',
            'билеты', 'медкнижка', 'диплом', 'удостоверение', 'фио', 'фамилия',
            'имя', 'отчество'
        ]
        print(f"{Fore.YELLOW}⚠️  Ключевые слова из файла не загружены. Используются стандартные.")
        return default_terms

    def scan_folder(self):
        """Сканирует папку с подсчетом файлов и интерактивным прогрессом."""
        if not self.folder_path.exists():
            self.errors.append(f"Путь {self.folder_path} не существует.")
            return

        print(f"{Fore.GREEN}🔍 Начинаем сканирование: {self.folder_path}")
        
        # Подсчет общего количества файлов
        total_files_count = 0
        try:
            for root, dirs, files in os.walk(self.folder_path):
                total_files_count += len(files)
            print(f"{Fore.GREEN}✅ Подсчет завершен. Найдено файлов для проверки: {total_files_count}")
        except Exception as e:
            self.errors.append(f"⚠️ Не удалось подсчитать общее количество файлов: {e}")
        
        total_files = [total_files_count]
        processed_files = [0]
        
        progress_thread = threading.Thread(target=scan_progress, args=(total_files, processed_files))
        progress_thread.daemon = True 
        progress_thread.start()
        
        try:
            for root, dirs, files in os.walk(self.folder_path):
                for file in files:
                    full_path = Path(root) / file
                    self._process_file(full_path)
                    processed_files[0] += 1
                
                for i in range(len(dirs)-1, -1, -1):
                    dir_path = Path(root) / dirs[i]
                    if not os.access(dir_path, os.R_OK):
                        self.errors.append(f"⚠️ Нет доступа к папке: {dir_path}. Пропуск.")
                        dirs.pop(i)
                        
        except Exception as e:
            self.errors.append(f"❗ Критическая ошибка при сканировании: {e}")
            
        finally:
            print("\r" + " " * 60, end='\r')
            print("\rСканирование завершено. " + " " * 40)
            
    def _process_file(self, file_path):
        filename = file_path.name.lower()
        
        for term in self.SEARCH_TERMS:
            if term in filename:
                try:
                    file_size = file_path.stat().st_size
                    created_time = datetime.fromtimestamp(file_path.stat().st_ctime)
                    last_modified = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    owner_login, editor_login = ("Неизвестно", "Неизвестно")
                    if pywin32_available:
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
                    break
                except Exception as e:
                    self.errors.append(f"⚠️ Ошибка обработки '{file_path.name}': {e}")
    
    def _get_owners_from_dacl(self, file_path):
        """Анализирует DACL файла."""
        owner_login = "Неизвестно"
        editor_login = "Неизвестно"
        
        try:
            sd = win32security.GetFileSecurity(
                str(file_path),
                win32security.OWNER_SECURITY_INFORMATION | win32security.DACL_SECURITY_INFORMATION
            )
            
            owner_sid = sd.GetSecurityDescriptorOwner()
            name, domain, _ = win32security.LookupAccountSid(None, owner_sid)
            owner_login = f"{domain}\\{name}" if name else "Неизвестно"
            
            dacl = sd.GetSecurityDescriptorDacl()
            if dacl:
                for i in range(dacl.GetAceCount()):
                    ace = dacl.GetAce(i)
                    if ace[0][0] == ntsecuritycon.ACCESS_ALLOWED_ACE_TYPE and ace[0][1] & ntsecuritycon.FILE_WRITE_DATA:
                        sid = ace[2]
                        name, domain, _ = win32security.LookupAccountSid(None, sid)
                        editor_login = f"{domain}\\{name}" if name else "Неизвестно"
                        break 
                        
        except Exception:
            pass 
            
        return owner_login, editor_login

    def _get_file_icon(self, ext):
        return self.FILE_ICONS.get(ext.lower(), '📁')
    
    def generate_report(self):
         """Выводит отчёт в консоль."""
         print("\n" + "="*80)
         print(f"{Fore.MAGENTA}🔍 ОТЧЁТ О РЕЗУЛЬТАТАХ АУДИТА")
         print("="*80 + Style.RESET_ALL)
 
         if self.errors:
             print(f"{Fore.RED}⚠️ ОБНАРУЖЕНЫ ОШИБКИ:")
             for i, error in enumerate(self.errors, 1):
                 print(f"{i}. {error}")
             print()
 
         has_data = len(self.results) > 0 or len(self.errors) > 0

         if not has_data:
             print(f"{Fore.BLUE}ℹ️ Папка пуста или не содержит файлов для проверки.")
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
 
    def _save_report(self, content, filename):
         """Сохраняет отчет с обработкой ошибок доступа."""
         report_dir = Path(r"C:\Users\kholostykh.iuv\Desktop\FileAuditor")
         report_dir.mkdir(exist_ok=True)
         
         report_filename = report_dir / filename
         try:
             with open(report_filename, 'w', encoding='utf-8') as f:
                 f.write(content)
             print(f"{Fore.GREEN}✅ Отчёт успешно сохранён в файл: {report_filename}")
             return True
         except PermissionError as e:
             error_msg = f"{Fore.RED}❌ Ошибка записи! Нет прав на сохранение файла в папку {report_dir}."
             print(error_msg)
             return False
         except Exception as e:
             error_msg = f"{Fore.RED}❌ Неизвестная ошибка при сохранении файла: {e}"
             print(error_msg)
             return False

    def save_to_txt(self):
         if len(self.results) == 0 and len(self.errors) == 0:
             return

         content = (
             "="*80 + "\n"
             "🔍 ОТЧЁТ О РЕЗУЛЬТАТАХ АУДИТА\n"
             "="*80 + "\n\n"
             f"Путь к папке: {self.folder_path}\n"
             f"Пользователь: {getpass.getuser()}\n"
             f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
         )
 
         if self.errors:
             content += "⚠️ ОШИБКИ:\n"
             for error in self.errors:
                 content += f"- {error}\n"
             content += "\n"
 
         if self.results:
             content += "✅ НАЙДЕНО ФАЙЛОВ:\n"
             sorted_results = sorted(self.results, key=lambda x: x['modified_date'], reverse=True)
             for item in sorted_results:
                 content += (f"{item['icon']} Файл: {item['filename']}\n"
                             f"Путь: {item['path']}\n"
                             f"Размер: {item['size_kb']} KB\n"
                             f"Создан: {item['created_date']} | Создатель: {item['creator_login']}\n"
                             f"Изменен: {item['modified_date']} | Редактор: {item['editor_login']}\n"
                             f"Ключевое слово: '{item['keyword_found']}'\n\n")
 
         content += "="*80 + "\nКонец отчёта\n"
         
         return self._save_report(content, "audit_report.txt")
             
    def save_to_csv(self):
         if not pandas_available or len(self.results) == 0 and len(self.errors) == 0:
             return

         try:
             df = pd.DataFrame(self.results)
             
             columns_order = ['icon', 'filename', 'path', 'size_kb', 
                             'created_date', 'creator_login',
                             'modified_date', 'editor_login',
                             'keyword_found']
             
             df_sorted = df.sort_values(by='modified_date', ascending=False)[columns_order]
             
             from io import StringIO
             buffer = StringIO()
             df_sorted.to_csv(buffer, index=False, encoding='utf-8')
             
             csv_content = buffer.getvalue()
             
             if self.errors:
                 csv_content += "\n# --- ОШИБКИ ВО ВРЕМЯ СКАНИРОВАНИЯ ---\n"
                 for error in self.errors:
                     clean_error = error.replace('\n', '\\n').replace(',', ';')
                     csv_content += clean_error + "\n"
                     
         except Exception as e:
             print(f"{Fore.RED}❌ Ошибка при подготовке данных CSV: {e}")
             return

         return self._save_report(csv_content, "audit_report.csv")
             
    def save_to_excel(self):
         """Сохраняет отчет в формате Excel (.xlsx)."""
         if not pandas_available or len(self.results) == 0 and len(self.errors) == 0:
              return

         report_filename = Path(r"C:\Users\kholostykh.iuv\Desktop\FileAuditor") / "audit_report.xlsx"
         
         try:
             df = pd.DataFrame(self.results)
             
             columns_order = ['icon', 'filename', 'path', 'size_kb', 
                             'created_date', 'creator_login',
                             'modified_date', 'editor_login',
                             'keyword_found']
             
             df_sorted = df.sort_values(by='modified_date', ascending=False)[columns_order]
             
             df_sorted.to_excel(report_filename, index=False)
             
         except PermissionError as e:
              error_msg = f"{Fore.RED}❌ Ошибка записи! Нет прав на сохранение файла в папку."
              print(error_msg)
              return False
         except Exception as e:
              print(f"{Fore.RED}❌ Ошибка при сохранении Excel: {e}")
              return False

         print(f"{Fore.GREEN}✅ Отчёт успешно сохранён в файл: {report_filename}")
         return True
             
    def save_to_pdf(self):
         """Сохраняет отчет в PDF-файл."""
         if not fpdf2_available or len(self.results) == 0 and len(self.errors) == 0:
              return

         report_filename = Path(r"C:\Users\kholostykh.iuv\Desktop\FileAuditor") / "audit_report.pdf"
         
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
                 for error in self.errors[:5]:
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
                 
                 sorted_results = sorted(self.results, key=lambda x: x['modified_date'], reverse=True)[:15]
                 
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
             
         except PermissionError as e:
              error_msg = f"{Fore.RED}❌ Ошибка записи! Нет прав на сохранение файла в папку."
              print(error_msg)
              return False
         except Exception as e:
              print(f"{Fore.RED}❌ Ошибка при сохранении PDF: {e}")
              return False

         print(f"{Fore.GREEN}✅ Отчёт успешно сохранён в файл: {report_filename}")
         return True


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


def show_description():
     os.system('cls' if os.name == 'nt' else 'clear')
     print("=" * 65)
     print("🛡️ FileAuditor Pro v3.0 - Краткое описание и возможности")
     print("=" * 65)
     print("- Использует локальные библиотеки из C:\\Users\\kholostykh.iuv\\Desktop\\FileAuditor.")
     print("- Сканирует папки с интерактивным прогрессом.")
     print("- Анализирует DACL для определения создателя и редактора файла.")
     input("\nНажмите Enter для возврата в меню...")
 
def main():
     while True:
         os.system('cls' if os.name == 'nt' else 'clear')
         print("=" * 55)
         print("🛡️ FileAuditor Pro v3.0 - Главное меню")
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