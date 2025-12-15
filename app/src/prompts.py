def build_system_prompts(current_time_taipei: str) -> list[dict]:
    base = [
        {"text": "You are a helpful and professional DevOps/SRE Assistant."},
        {"text": "You should answer questions concisely and use technical terminology where appropriate."},
    ]
    time_prompt = {"text": f"The current time in Taipei is {current_time_taipei}."}
    return base + [time_prompt]
