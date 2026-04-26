import os
import sys
import getpass
import time
import threading
import csv
import json
from datetime import datetime
from pathlib import Path

# --- 1. ПОДКЛЮЧЕНИЕ ЛОКАЛЬНЫХ БИБЛИОТЕК (автопоиск всех подпапок) ---
BASE_DIR = Path(r"C:/Users/kholostykh.iuv/Desktop/FileAuditor")

LIB_PATHS = {
    'colorama':      BASE_DIR / "colorama-master",
    'fpdf2':         BASE_DIR / "fpdf2-master",
    'numpy':         BASE_DIR / "numpy-2.4.4",
    'pandas':        BASE_DIR / "pandas-3.0.2",
    'pywin32':       BASE_DIR / "pywin32-b311",
    'tqdm':          BASE_DIR / "tqdm-master",
    'progress':      BASE_DIR / "python-progress-main",
    'alive_progress': BASE_DIR / "alive-progress-main",
}

def add_library_to_syspath(base_path):
    """Добавляет корень библиотеки и все её подпапки с __init__.py в sys.path."""
    if not base_path.exists():
        return
    # Сначала добавляем саму папку – это важно для colorama и подобных
    sys.path.insert(0, str(base_path))
    # Теперь рекурсивно ищем все вложенные папки, содержащие __init__.py
    for dirpath, dirnames, filenames in os.walk(base_path):
        if '__init__.py' in filenames:
            sys.path.insert(0, dirpath)

for path in LIB_PATHS.values():
    add_library_to_syspath(path)

# --- 2. ПРОВЕРКА НАЛИЧИЯ БИБЛИОТЕК ---
HAS_COLORAMA = False
HAS_PROGRESS = False
HAS_TQDM = False
HAS_ALIVE = False

fpdf2_available = False
pandas_available = False
pywin32_available = False

class FallbackColors:
    GREEN = ""
    RED = ""
    CYAN = ""
    MAGENTA = ""
    BLUE = ""
    YELLOW = ""
    RESET_ALL = ""

Fore = FallbackColors()
Style = FallbackColors()

try:
    import colorama
    colorama.init(autoreset=True)
    from colorama import Fore, Style
    HAS_COLORAMA = True
except ImportError:
    pass

try:
    import progress.bar as progress_bar
    HAS_PROGRESS = True
except ImportError:
    pass

try:
    import tqdm
    HAS_TQDM = True
except ImportError:
    pass

# alive_progress: сначала зависимость about_time
try:
    import about_time
except ImportError:
    # ищем около alive-progress
    abt_path = BASE_DIR / "alive-progress-main" / "about_time"
    if abt_path.exists():
        sys.path.insert(0, str(abt_path))
    else:
        abt_file = BASE_DIR / "alive-progress-main" / "about_time.py"
        if abt_file.exists():
            sys.path.insert(0, str(abt_file.parent))
    try:
        import about_time
    except ImportError:
        pass

try:
    import alive_progress as alive_progress_main
    HAS_ALIVE = True
except ImportError:
    HAS_ALIVE = False

try:
    from fpdf2 import FPDF
    fpdf2_available = True
except ImportError:
    print(f"{Fore.YELLOW}⚠️  Библиотека fpdf2 не найдена. Сохранение в PDF будет недоступно.")

try:
    import win32security
    import ntsecuritycon
    pywin32_available = True
except ImportError:
    print(f"{Fore.YELLOW}⚠️  Библиотека pywin32 не найдена. Анализ владельцев файлов будет недоступен.")


class FileAuditorPro:
    FILE_ICONS = {
        '.pdf': '📑', '.doc': '📝', '.docx': '📝',
        '.xls': '📊', '.xlsx': '📊', '.jpg': '🖼️',
        '.jpeg': '🖼️', '.png': '🖼️', '.txt': '📜',
        '.zip': '🗜️', '.rar': '🗜️', '.exe': '⚙️'
    }

    TEXT_EXTENSIONS = {
        '.txt', '.csv', '.log', '.xml', '.json', '.html', '.htm',
        '.py', '.md', '.js', '.css', '.yaml', '.yml', '.ini', '.cfg'
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
                if HAS_PROGRESS:
                    with open(self.keywords_file, 'r', encoding='utf-8') as f:
                        lines = sum(1 for _ in f)
                    bar = progress_bar.IncrementalBar(
                        'Загрузка ключевых слов', max=lines, suffix='%(percent)d%%'
                    )
                else:
                    bar = None
                with open(self.keywords_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        word = line.strip().lower()
                        if word and not word.startswith('#'):
                            terms.append(word)
                        if bar:
                            bar.next()
                if bar:
                    bar.finish()
                print(f"{Fore.GREEN}✅ Загружено {len(terms)} ключевых слов.")
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

    def _get_file_owner(self, file_path):
        if not pywin32_available:
            return "N/A"
        try:
            sd = win32security.GetFileSecurity(str(file_path), win32security.OWNER_SECURITY_INFORMATION)
            owner_sid = sd.GetSecurityDescriptorOwner()
            name, domain, type = win32security.LookupAccountSid(None, owner_sid)
            return f"{domain}\\{name}" if domain else name
        except Exception:
            return "Ошибка"

    def _contains_keywords(self, text, keywords):
        text_lower = text.lower()
        return [kw for kw in keywords if kw in text_lower]

    def _process_file(self, file_path):
        matched_kws = []
        match_type = ""

        name_matches = self._contains_keywords(file_path.name, self.SEARCH_TERMS)
        if name_matches:
            matched_kws = name_matches
            match_type = "имя файла"

        ext = file_path.suffix.lower()
        if ext in self.TEXT_EXTENSIONS:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(1024 * 1024)
                content_matches = self._contains_keywords(content, self.SEARCH_TERMS)
                if content_matches:
                    if match_type:
                        match_type += "+содержимое"
                    else:
                        match_type = "содержимое"
                    matched_kws = list(set(matched_kws + content_matches))
            except Exception:
                pass

        if matched_kws:
            owner = self._get_file_owner(file_path)
            stat = file_path.stat() if file_path.exists() else None
            result = {
                'path': str(file_path),
                'filename': file_path.name,
                'matched_keywords': ', '.join(matched_kws),
                'match_type': match_type,
                'owner': owner,
                'size': stat.st_size if stat else 0,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat() if stat else ''
            }
            self.results.append(result)

    def scan_folder(self):
        if not self.folder_path.exists():
            self.errors.append(f"Путь {self.folder_path} не существует.")
            return

        print(f"\n{Fore.GREEN}🔍 Сбор списка файлов: {self.folder_path}")
        print(f"{Fore.CYAN}(Это может занять время на больших/сетевых папках...)")
        all_files = []
        file_count = 0
        last_print_time = time.time()
        try:
            for root, dirs, files in os.walk(self.folder_path, onerror=lambda e: None):
                for file in files:
                    all_files.append((root, file))
                    file_count += 1
                now = time.time()
                if now - last_print_time >= 5 or file_count % 2000 == 0:
                    print(f"\rНайдено файлов: {file_count}...", end="", flush=True)
                    last_print_time = now
        except Exception as e:
            self.errors.append(f"⚠️ Ошибка при составлении списка файлов: {e}")
            return

        total_files_count = len(all_files)
        print(f"\rНайдено файлов: {total_files_count}    ")
        if total_files_count == 0:
            print(f"{Fore.YELLOW}Папка пуста.")
            return

        print(f"{Fore.GREEN}🔍 Начинаем сканирование: {self.folder_path}")
        print(f"{Fore.CYAN}Всего файлов: {total_files_count}")

        use_advanced = False
        if HAS_TQDM and HAS_ALIVE:
            try:
                with tqdm.tqdm(total=total_files_count, desc="Сканирование папки",
                               unit="файл", ncols=100) as pbar_main:
                    with alive_progress_main.alive_bar(total_files_count,
                                                       title="Поиск совпадений") as a_bar:
                        for root, file in all_files:
                            full_path = Path(root) / file
                            self._process_file(full_path)
                            pbar_main.update(1)
                            a_bar()
                use_advanced = True
            except Exception as e:
                self.errors.append(f"⚠️ Ошибка при использовании прогресс-баров: {e}")
                print(f"{Fore.YELLOW}⚠️  Переключаемся на упрощённый режим.")

        if not use_advanced:
            if total_files_count > 0:
                missing_libs_info = []
                if not HAS_TQDM:
                    missing_libs_info.append("tqdm")
                if not HAS_ALIVE:
                    missing_libs_info.append("alive-progress")
                if missing_libs_info:
                    print(f"{Fore.YELLOW}⚠️  Не найдены библиотеки: {', '.join(missing_libs_info)}. "
                          "Работаем в упрощенном режиме.")
                for i, (root, file) in enumerate(all_files):
                    full_path = Path(root) / file
                    self._process_file(full_path)
                    if (i + 1) % 100 == 0 or (i + 1) == total_files_count:
                        print(f"\rОбработано {i + 1}/{total_files_count} файлов", end="", flush=True)
                print()

    def save_report_csv(self, output_path):
        try:
            with open(output_path, 'w', newline='', encoding='utf-8-sig') as cf:
                fieldnames = ['path', 'filename', 'matched_keywords', 'match_type', 'owner', 'size', 'modified']
                writer = csv.DictWriter(cf, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.results)
            print(f"{Fore.GREEN}📁 CSV сохранён: {output_path}")
        except Exception as e:
            print(f"{Fore.RED}Ошибка сохранения CSV: {e}")

    def save_report_txt(self, output_path):
        try:
            with open(output_path, 'w', encoding='utf-8') as tf:
                tf.write("=== Результаты FileAuditor Pro ===\n")
                tf.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                tf.write(f"Папка сканирования: {self.folder_path}\n")
                tf.write(f"Всего совпадений: {len(self.results)}\n\n")
                for i, res in enumerate(self.results, 1):
                    tf.write(f"{'─'*50}\n")
                    tf.write(f"#{i}  Файл: {res['filename']}\n")
                    tf.write(f"   Путь: {res['path']}\n")
                    tf.write(f"   Ключевые слова: {res['matched_keywords']}\n")
                    tf.write(f"   Тип совпадения: {res['match_type']}\n")
                    tf.write(f"   Владелец: {res['owner']}\n")
                    tf.write(f"   Размер: {res['size']} байт\n")
                    tf.write(f"   Изменён: {res['modified']}\n")
            print(f"{Fore.GREEN}📁 TXT сохранён: {output_path}")
        except Exception as e:
            print(f"{Fore.RED}Ошибка сохранения TXT: {e}")

    def save_report_pdf(self, output_path):
        if not fpdf2_available:
            print(f"{Fore.RED}PDF‑сохранение невозможно: fpdf2 не найден.")
            return
        try:
            pdf = FPDF()
            pdf.add_page()
            # Шрифт с поддержкой кириллицы (если есть в системе)
            font_path = r'C:\Windows\Fonts\DejaVuSans.ttf'
            if not os.path.exists(font_path):
                # запасной вариант – можно попробовать другой шрифт
                font_path = None
            if font_path:
                pdf.add_font('DejaVu', '', font_path, uni=True)
                pdf.set_font('DejaVu', '', 10)
            else:
                pdf.set_font('Arial', '', 10)

            pdf.cell(0, 10, 'Результаты FileAuditor Pro', ln=True)
            pdf.ln(5)
            for i, res in enumerate(self.results, 1):
                pdf.set_font('DejaVu' if font_path else 'Arial', '', 8)
                pdf.cell(0, 5, f"{i}. {res['filename']} [{res['match_type']}]", ln=True)
                pdf.cell(0, 5, f"   Ключевые слова: {res['matched_keywords']}", ln=True)
                pdf.cell(0, 5, f"   Путь: {res['path']}", ln=True)
                if i >= 100:
                    pdf.cell(0, 5, '... (вывод ограничен 100 записями)', ln=True)
                    break
            pdf.output(output_path)
            print(f"{Fore.GREEN}📁 PDF сохранён: {output_path}")
        except Exception as e:
            print(f"{Fore.RED}Ошибка сохранения PDF: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="File Auditor Pro – поиск конфиденциальных файлов")
    parser.add_argument("folder", nargs="?", default=None,
                        help="Путь к папке для сканирования (если не указан, будет запрошен)")
    parser.add_argument("-k", "--keywords", help="Файл с ключевыми словами (опционально)", default=None)

    try:
        args = parser.parse_args()
    except SystemExit:
        args = parser.parse_args([])

    if args.folder is None:
        print(f"\n{Fore.CYAN}Укажите путь к папке для сканирования.{Style.RESET_ALL}")
        folder_input = input("Путь: ").strip().strip('"')
        if not folder_input:
            print(f"{Fore.RED}Путь не указан, завершение работы.")
            sys.exit(1)
    else:
        folder_input = args.folder

    if args.keywords is None:
        print(f"\n{Fore.CYAN}Укажите путь к файлу с ключевыми словами{Style.RESET_ALL}")
        print(f"{Fore.CYAN}(или просто нажмите Enter, чтобы использовать стандартный список).{Style.RESET_ALL}")
        kw_input = input("Файл ключевых слов: ").strip().strip('"')
        keywords_file_input = kw_input if kw_input else None
    else:
        keywords_file_input = args.keywords

    auditor = FileAuditorPro(folder_input, keywords_file_input)
    auditor.scan_folder()

    if auditor.results:
        print(f"\n{Fore.GREEN}✅ Найдено совпадений: {len(auditor.results)}")
        for i, res in enumerate(auditor.results[:20], 1):
            print(f"\n{Fore.CYAN}--- Результат {i} ---")
            print(f"  Файл: {Fore.YELLOW}{res['filename']}")
            print(f"  Путь: {res['path']}")
            print(f"  Ключевые слова: {Fore.MAGENTA}{res['matched_keywords']}")
            print(f"  Тип совпадения: {res['match_type']}")
            print(f"  Владелец: {res['owner']}")
            print(f"  Размер: {res['size']} байт")
            print(f"  Изменён: {res['modified']}")
        if len(auditor.results) > 20:
            print(f"\n... и ещё {len(auditor.results)-20}")

        # --- Сохранение отчёта ---
        print(f"\n{Fore.CYAN}Доступные форматы: CSV, TXT")
        if fpdf2_available:
            print(f"{Fore.CYAN}                 : PDF")
        else:
            print(f"{Fore.YELLOW}(PDF недоступен – нет fpdf2)")

        choice = input(f"{Fore.CYAN}Введите формат (csv/txt/pdf) или Enter для пропуска: {Style.RESET_ALL}").strip().lower()
        if choice in ('csv', 'txt', 'pdf'):
            default_name = f"audit_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            ext = '.' + choice
            default_path = Path.cwd() / (default_name + ext)

            print(f"{Fore.CYAN}Путь сохранения (Enter = {default_path}): {Style.RESET_ALL}")
            user_path = input().strip().strip('"')
            if not user_path:
                save_path = default_path
            else:
                user_path = Path(user_path)
                if user_path.is_dir():
                    save_path = user_path / (default_name + ext)
                else:
                    save_path = user_path

            save_path.parent.mkdir(parents=True, exist_ok=True)

            if choice == 'csv':
                auditor.save_report_csv(str(save_path))
            elif choice == 'txt':
                auditor.save_report_txt(str(save_path))
            elif choice == 'pdf':
                auditor.save_report_pdf(str(save_path))
        else:
            print("Сохранение пропущено.")
    else:
        print(f"{Fore.YELLOW}Совпадений не найдено.")

    if auditor.errors:
        print(f"\n{Fore.RED}Ошибки при выполнении:")
        for err in auditor.errors:
            print(f" - {err}")