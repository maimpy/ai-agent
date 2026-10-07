import os

# Глобальна змінна для робочої папки агента
CURRENT_WORK_DIR = os.getcwd()

def set_work_dir(path):
    """Встановлює робочу директорію для файлових операцій агента."""
    global CURRENT_WORK_DIR
    if path and os.path.exists(path):
        CURRENT_WORK_DIR = path
        os.chdir(path)

# --- Файлові інструменти для LLM Tool-Calling ---

def read_file(filepath):
    """Читає вміст текстового файлу відносно поточної робочої директорії."""
    try:
        full_path = filepath if os.path.isabs(filepath) else os.path.join(CURRENT_WORK_DIR, filepath)
        if not os.path.exists(full_path):
            return f"Помилка: Файл '{filepath}' не знайдено у директорії {CURRENT_WORK_DIR}."
        
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Помилка читання файлу: {str(e)}"

def write_file(filepath, content):
    """Створює новий файл або перезаписує існуючий у робочій директорії агента."""
    try:
        full_path = filepath if os.path.isabs(filepath) else os.path.join(CURRENT_WORK_DIR, filepath)
        os.makedirs(os.path.dirname(os.path.abspath(full_path)), exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Успішно записано файл: {filepath} у паку {CURRENT_WORK_DIR}"
    except Exception as e:
        return f"Помилка запису файлу: {str(e)}"

def list_files():
    """Показує список усіх файлів у робочій директорії."""
    try:
        files = os.listdir(CURRENT_WORK_DIR)
        return f"Список файлів у пачці {CURRENT_WORK_DIR}: {files}"
    except Exception as e:
        return f"Помилка: {str(e)}"

# Мапа доступних функцій для AI інструментів
available_functions = {
    "read_file": read_file,
    "write_file": write_file,
    "list_files": list_files
}

# Опис інструментів у форматі OpenAI Tools для LiteLLM
tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Читає вміст текстового файлу в робочій директорії агента.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Шлях до файлу відносно робочої папки"
                    }
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Створює новий файл або перезаписує існуючий у робочій директорії агента.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Шлях до файлу для збереження"
                    },
                    "content": {
                        "type": "string",
                        "description": "Текстовий вміст (код або текст), який потрібно записати"
                    }
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Показує список усіх файлів у поточній робочій директорії агента, щоб знати, які файли існують.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

def load_system_rules():
    """Завантажує системні правила з файлу rules.md, якщо він існує."""
    rules_path = os.path.join(os.getcwd(), "rules.md")
    if os.path.exists(rules_path):
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return "Дотримуйся чистоти коду, пиши надійні рішення та використовуй інструменти для роботи з файлами."