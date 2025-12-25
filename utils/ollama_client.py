from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from typing import List, Optional, Tuple, Any
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.settings import ModelSettings
from openai.types import chat
from tools.loader import register_all

class OllamaCompatibleOpenAIModel(OpenAIChatModel):
    """
    Либо Ollama, либо pydantic_ai при наличии tool_calls и отсутствии текста 
    передают 'content': null. Ollama на это ругается: 'invalid message content type: <nil>'.
    Этот хак заменяет null на пустую строку.
    """
    def _map_model_response(self, message: ModelResponse) -> chat.ChatCompletionMessageParam:
        res = super()._map_model_response(message)
        # Если это сообщение ассистента и контент пустой, заменяем None на ""
        if res.get('role') == 'assistant' and res.get('content') is None:
            res['content'] = ''
        
        # FIX: Pydantic-AI validation error if role is missing/empty
        if not res.get('role'):
            res['role'] = 'assistant'
            
        return res

DEBUG = False

def set_debug(value: bool):
    global DEBUG
    DEBUG = value

def build_agent(system_prompt: Optional[str] = None, use_tools: bool = True) -> Agent:
    model = OllamaCompatibleOpenAIModel(
        # "qwen2.5-coder:7b-instruct",
        # "llama3.1:8b",
        # "qwen2.5:7b-instruct",
        # "qwen2.5-coder:14b-instruct-q2_K",
        # "hermes3",
        "llama3.1:8b-instruct-q5_K_M",
        provider=OpenAIProvider(
            base_url="http://127.0.0.1:11434/v1",
            api_key="ollama",
        ),
    )
    
    # Используем переданный системный промпт или дефолтный
    default_system_prompt = """
    Ты работаешь в роли API Test Generator и Endpoint Analyst.
    """
    
    final_system_prompt = system_prompt if system_prompt is not None else default_system_prompt
    
    agent = Agent(
        model, 
        system_prompt=final_system_prompt,
        model_settings=ModelSettings(temperature=0)
    )
    
    if use_tools:
        register_all(agent)  # автоподхват всех tools/*
    
    return agent

_agents = {}  # Кеш агентов по (hash(system_prompt), use_tools)

def send_messages(
    user_message: str,
    history: Optional[List[ModelMessage]] = None,
    system_prompt: Optional[str] = None,
    use_tools: bool = True,
    step_name: Optional[str] = None,
    model_settings: Optional[ModelSettings] = None,
) -> Tuple[str, List[ModelMessage]]:
    global _agents, DEBUG

    # Используем хэш системного промпта и флаг использования инструментов как ключ для кеширования
    prompt_key = (hash(system_prompt) if system_prompt else "default", use_tools)

    # Создаем агента только если его нет в кеше
    if prompt_key not in _agents:
        _agents[prompt_key] = build_agent(system_prompt, use_tools=use_tools)

    agent = _agents[prompt_key]
    
    if DEBUG:
        print(f"{'='*60}")
        print(f"Модель получила сообщение (use_tools={use_tools}): {user_message}")
        print(f"{'='*60}")
    elif step_name:
        print(f">>> Шаг: {step_name}")

    try:
        if history is not None:
            result = agent.run_sync(
                user_message, 
                message_history=history,
                model_settings=model_settings
            )
        else:
            result = agent.run_sync(
                user_message,
                model_settings=model_settings
            )
        
        print(f"Модель ответила: {result.output}")
        return result.output, result.all_messages()
    except Exception as e:
        print(f"ОШИБКА ПРИ ВЫЗОВЕ МОДЕЛИ: {e}")
        # Если произошла ошибка 400, это может быть из-за застрявшего состояния или проблем с Ollama
        raise
