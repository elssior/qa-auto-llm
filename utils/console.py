"""
Утилиты для красивого вывода в консоль
"""

class Colors:
    """ANSI цвета для терминала"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Цвета текста
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Яркие цвета
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'


def print_header(text):
    """Красивый заголовок"""
    print(f"\n{Colors.BOLD}{Colors.BRIGHT_CYAN}{'═' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BRIGHT_CYAN} {text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BRIGHT_CYAN}{'═' * 60}{Colors.RESET}\n")


def print_step(step_num, title):
    """Заголовок шага"""
    print(f"\n{Colors.BOLD}{Colors.BRIGHT_BLUE}[{step_num}] {title}{Colors.RESET}")
    print(f"{Colors.BLUE}{'─' * 50}{Colors.RESET}")


def print_substep(substep, title):
    """Подшаг"""
    print(f"\n  {Colors.CYAN}► {substep}: {title}{Colors.RESET}")


def print_success(message):
    """Успешное сообщение"""
    print(f"  {Colors.BRIGHT_GREEN}✓{Colors.RESET} {message}")


def print_info(message):
    """Информационное сообщение"""
    print(f"  {Colors.CYAN}ℹ{Colors.RESET} {message}")


def print_warning(message):
    """Предупреждение"""
    print(f"  {Colors.BRIGHT_YELLOW}⚠{Colors.RESET} {message}")


def print_error(message):
    """Ошибка"""
    print(f"  {Colors.BRIGHT_RED}✗{Colors.RESET} {message}")


def print_tool_call(tool_name, arg_preview):
    """Вызов инструмента"""
    print(f"  {Colors.MAGENTA}🔧{Colors.RESET} {tool_name}: {arg_preview}")


def print_model_response(text, max_length=100):
    """Ответ модели (укороченный)"""
    if len(text) > max_length:
        preview = text[:max_length] + "..."
    else:
        preview = text
    print(f"  {Colors.WHITE}💬{Colors.RESET} {preview}")
