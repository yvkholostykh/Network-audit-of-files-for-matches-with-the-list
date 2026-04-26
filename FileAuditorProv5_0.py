import os
import sys
import getpass
import time
import threading
import csv
from datetime import datetime
from pathlib import Path

# --- 1. ПОДКЛЮЧЕНИЕ ЛОКАЛЬНЫХ БИБЛИОТЕК ---
BASE_DIR = Path(r"C:/Users/kholostykh.iuv/Desktop/FileAuditor")

LIB_PATHS = {
    'colorama': BASE_DIR / "colorama-master",
    'fpdf2': BASE_DIR / "fpdf2-master",
    'numpy': BASE_DIR / "numpy-2.4.4",
    'pandas': BASE_DIR / "pandas-3.0.2",
    'pywin32': BASE_DIR / "pywin32-b311",
    'tqdm': BASE_DIR / "tqdm-master",
    'progress': BASE_DIR / "python-progress-main",
    'alive_progress': BASE_DIR / "alive-progress-main",
}

for path in LIB_PATHS.values():
    if path.exists() and path.is_dir():
        sys.path.insert(0, str(path))

# --- 2. ПРОВЕРКА НАЛИЧИЯ БИБЛИОТЕК И ВЫБОР РЕЖИМА ---
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

try:
    import alive_progress as alive_progress_main
    # Проверяем зависимость about_time
    import about_time
    HAS_ALIVE = True
except ImportError:
    try:
        sys.path.insert(0, str(BASE_DIR / "alive-progress-main" / "src"))
        import alive_progress as alive_progress_main
        import about_time
        HAS_ALIVE = True
    except Exception:
        HAS_ALIVE = False

try:
    from fpdf2 import FPDF
    fpdf2_available = True
except ImportError:
    print(f"{Fore.YELLOW}⚠️  Библиотека fpdf2 не найдена. Сохранение в PDF будет недоступно.")

try:
    import pandas as pd
    pandas_available = True
except ImportError:
    print(f"{Fore.YELLOW}⚠️  Библиотека pandas не найдена. Сохранение в CSV/Excel будет недоступно.")

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

    # Расширения, которые считаем текстовыми
    TEXT_EXTENSIONS = {
        '.txt', '.csv', '.log', '.xml', '.json', '.html', '.htm',
        '.py', '.md', '.js', '.css', '.yaml', '.yml', '.ini', '.cfg'
    }

    def __init__(self, folder_path, keywords_file=None):
        self.folder_path = Path(folder_path).resolve()
        self.keywords_file = Path(keywords_file).resolve() if keywords_file else None
        self.results = []       # список словарей с находками
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
        """Возвращает владельца файла (Windows)."""
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
        """Проверяет, есть ли хотя бы одно ключевое слово в тексте (без учёта регистра)."""
        text_lower = text.lower()
        return [kw for kw in keywords if kw in text_lower]

    def _process_file(self, file_path):
        """
        Проверяет имя файла и (для текстовых) содержимое на наличие ключевых слов.
        Результаты добавляет в self.results.
        """
        matched_kws = []
        match_type = ""

        # 1. Проверка имени файла
        name_matches = self._contains_keywords(file_path.name, self.SEARCH_TERMS)
        if name_matches:
            matched_kws = name_matches
            match_type = "имя файла"

        # 2. Проверка содержимого (только для текстовых расширений)
        ext = file_path.suffix.lower()
        if ext in self.TEXT_EXTENSIONS:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(1024 * 1024)  # читаем первый мегабайт
                content_matches = self._contains_keywords(content, self.SEARCH_TERMS)
                if content_matches:
                    if match_type:
                        match_type += "+содержимое"
                    else:
                        match_type = "содержимое"
                    # объединяем ключевые слова, убираем дубли
                    matched_kws = list(set(matched_kws + content_matches))
            except Exception as e:
                # Не удалось прочитать – пропускаем
                pass

        if matched_kws:
            owner = self._get_file_owner(file_path)
            result = {
                'path': str(file_path),
                'filename': file_path.name,
                'matched_keywords': ', '.join(matched_kws),
                'match_type': match_type,
                'owner': owner,
                'size': file_path.stat().st_size if file_path.exists() else 0,
                'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat() if file_path.exists() else ''
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
        # Вывод первых 20 результатов
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

        # Сохранение в CSV (без pandas)
        try:
            csv_path = Path(folder_input) / f"audit_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(csv_path, 'w', newline='', encoding='utf-8-sig') as cf:
                fieldnames = ['path', 'filename', 'matched_keywords', 'match_type', 'owner', 'size', 'modified']
                writer = csv.DictWriter(cf, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(auditor.results)
            print(f"{Fore.GREEN}📁 Результаты сохранены в {csv_path}")
        except Exception as e:
            print(f"{Fore.RED}Ошибка при сохранении CSV: {e}")

    else:
        print(f"{Fore.YELLOW}Совпадений не найдено.")
    if auditor.errors:
        print(f"\n{Fore.RED}Ошибки при выполнении:")
        for err in auditor.errors:
            print(f" - {err}")