from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from typing import List, Optional, Tuple
from pydantic_ai.messages import ModelMessage
from tools.loader import register_all

def build_agent(system_prompt: Optional[str] = None) -> Agent:
    model = OpenAIChatModel(
        "qwen2.5:7b-instruct",
        provider=OpenAIProvider(
            base_url="http://127.0.0.1:11434/v1",
            api_key="ollama",
        ),
    )
    
    # Используем переданный системный промпт или дефолтный
    default_system_prompt = """
    Ты работаешь в роли API Test Generator и Endpoint Analyst.
    ...
    """
    
    final_system_prompt = system_prompt if system_prompt is not None else default_system_prompt
    
    agent = Agent(model, system_prompt=final_system_prompt)
    register_all(agent)  # автоподхват всех tools/*
    return agent

_agent = None  # Убираем глобального агента

def send_messages(
    user_message: str,
    history: Optional[List[ModelMessage]] = None,
    system_prompt: Optional[str] = None,
) -> Tuple[str, List[ModelMessage]]:
    global _agent
    
    # Создаем нового агента если системный промпт изменился
    if _agent is None or system_prompt is not None:
        _agent = build_agent(system_prompt)
    
    print(f"Модель получила сообщение: {user_message}")
    result = _agent.run_sync(user_message, message_history=history)
    print(f"Модель ответила: {result.output}")
    return result.output, result.all_messages()