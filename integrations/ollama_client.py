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

_agents = {}  # Кеш агентов по системным промптам

def send_messages(
    user_message: str,
    history: Optional[List[ModelMessage]] = None,
    system_prompt: Optional[str] = None,
) -> Tuple[str, List[ModelMessage]]:
    global _agents

    # Используем хэш системного промпта как ключ для кеширования
    prompt_key = hash(system_prompt) if system_prompt else "default"

    # Создаем агента только если его нет в кеше
    if prompt_key not in _agents:
        _agents[prompt_key] = build_agent(system_prompt)

    agent = _agents[prompt_key]
    
    print(f"{'='*60}")
    print(f"Модель получила сообщение: {user_message}")
    print(f"{'='*60}")

    if history is not None:
        result = agent.run_sync(user_message, message_history=history)
    else:
        result = agent.run_sync(user_message)

    print(f"Модель ответила: {result.output}")
    return result.output, result.all_messages()