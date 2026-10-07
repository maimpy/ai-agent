import os
import json
from litellm import completion
from config import load_system_rules, tools, available_functions

# Список актуальних моделей Gemini у порядку пріоритету
PREFERRED_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro"
]
# Параметри безпеки для повного зняття цензури та обмежень
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

def execute_ai_with_fallback(messages, provider_entries_getter=None, logger=None):
    if logger:
        logger("🔄 Запуск генерації через ланцюжок провайдерів...")
        
    user_keys = {}
    if provider_entries_getter:
        entries = provider_entries_getter()
        for env_key, data in entries.items():
            key_val = data["entry"].get().strip()
            if key_val:
                user_keys[env_key] = key_val
                os.environ[env_key] = key_val

    success = False
    final_answer = ""
    
    # 1. ЕТАП: Пробуємо Gemini із вашим списком PREFERRED_MODELS
    gemini_key = user_keys.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if gemini_key:
        os.environ["GEMINI_API_KEY"] = gemini_key
        for model_name in PREFERRED_MODELS:
            full_model = f"gemini/{model_name}"
            if logger:
                logger(f"🔄 Пробую провайдер: Google Gemini ({full_model})")
            
            try:
                response = completion(
                    model=full_model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    safety_settings=SAFETY_SETTINGS,
                    temperature=0.7
                )
                
                response_message = response.choices[0].message
                messages.append(response_message)

                # Безпечна обробка викликів інструментів (підтримка .args та .arguments)
                if hasattr(response_message, "tool_calls") and response_message.tool_calls:
                    for tool_call in response_message.tool_calls:
                        f_name = tool_call.function.name
                        
                        raw_args = getattr(tool_call.function, "arguments", None)
                        if raw_args is None:
                            raw_args = getattr(tool_call.function, "args", "{}")

                        if isinstance(raw_args, str):
                            try:
                                f_args = json.loads(raw_args)
                            except:
                                f_args = eval(raw_args) if raw_args else {}
                        else:
                            f_args = raw_args if isinstance(raw_args, dict) else {}
                        
                        if logger:
                            logger(f"⚙️ Виклик інструменту [{f_name}] з аргументами {f_args}")
                        
                        if f_name in available_functions:
                            output = available_functions[f_name](**f_args)
                            if logger:
                                logger(f"🔧 Результат: {output}")
                            
                            messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": f_name,
                                "content": str(output)
                            })
                    
                    second_response = completion(
                        model=full_model, 
                        messages=messages, 
                        safety_settings=SAFETY_SETTINGS,
                        temperature=0.7
                    )
                    
                    # Безпечне отримання тексту відповіді (запобігаємо появі None / "NONE")
                    second_msg = second_response.choices[0].message
                    final_answer = getattr(second_msg, "content", None)
                    if not final_answer:
                        final_answer = "✅ Дії з інструментами успішно виконано, але модель не повернула додаткового текстового коментаря."
                    messages.append(second_msg)
                else:
                    final_answer = response_message.content
                    if not final_answer:
                        final_answer = "✅ Запит опрацьовано."

                if logger:
                    logger(f"✅ Успішно виконано через Google Gemini ({model_name})")
                success = True
                break
            except Exception as e:
                err_msg = str(e).splitlines()[0] if str(e) else "Невідома помилка"
                if logger:
                    logger(f"⚠️ Модель {model_name} не спрацювала: {err_msg}. Пробую наступну...")
                continue

    if success:
        return final_answer

    # 2. ЕТАП: Резервні провайдери (Groq та OpenRouter)
    fallback_providers = [
        ("Groq", "GROQ_API_KEY", "groq/llama-3.1-8b-instant"),
        ("OpenRouter", "OPENROUTER_API_KEY", "openrouter/free")
    ]

    for p_name, env_k, model_m in fallback_providers:
        p_key = user_keys.get(env_k) or os.getenv(env_k)
        if not p_key:
            continue
            
        os.environ[env_k] = p_key
        if logger:
            logger(f"🔄 Перемикаюся на резервний провайдер: {p_name} ({model_m})...")

        try:
            response = completion(
                model=model_m,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.7
            )
            
            response_message = response.choices[0].message
            messages.append(response_message)

            if hasattr(response_message, "tool_calls") and response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    f_name = tool_call.function.name
                    raw_args = getattr(tool_call.function, "arguments", None) or getattr(tool_call.function, "args", "{}")
                    f_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    
                    if logger:
                        logger(f"⚙️ Виклик інструменту [{f_name}] з аргументами {f_args}")
                    
                    if f_name in available_functions:
                        output = available_functions[f_name](**f_args)
                        if logger:
                            logger(f"🔧 Результат: {output}")
                        
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": f_name,
                            "content": str(output)
                        })
                
                second_response = completion(model=model_m, messages=messages, temperature=0.7)
                second_msg = second_response.choices[0].message
                final_answer = getattr(second_msg, "content", None)
                if not final_answer:
                    final_answer = "✅ Дії виконано резервним провайдером."
                messages.append(second_msg)
            else:
                final_answer = response_message.content
                if not final_answer:
                    final_answer = "✅ Запит опрацьовано резервним провайдером."

            if logger:
                logger(f"✅ Успішно виконано через {p_name}")
            success = True
            break
        except Exception as e:
            if logger:
                logger(f"⚠ Збій у {p_name}: {str(e).splitlines()[0]}")
            continue

    if not success:
        raise Exception("❌ Жодна з моделей Gemini та резервні провайдери не змогли опрацювати запит.")

    return final_answer