import re
import textwrap

def strip_markdown(text):
    """Убирает markdown-разметку из текста, извлекая код из блоков."""
    if not text:
        return ""
    
    # Ищем блок кода ```...``` (с python или без)
    pattern = re.compile(r"```(?:python|json)?\s*(.*?)```", re.DOTALL)
    match = pattern.search(text)
    
    if match:
        code = match.group(1)
        # Сначала dedent (убирает общий отступ), потом strip
        return textwrap.dedent(code).strip()
        
    # Fallback: если блоков нет, но есть маркеры
    if "```" in text:
        code = text.replace("```python", "").replace("```json", "").replace("```", "")
        return textwrap.dedent(code).strip()

    # Если markdown нет - применяем dedent ко всему тексту
    # ВАЖНО: сначала dedent, потом strip!
    return textwrap.dedent(text).strip()
