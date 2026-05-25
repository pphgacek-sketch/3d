import openai
import time

def copilot_prompt(messages, max_tokens=2048, temperature=0.2, model="gpt-4o"):
    tries = 3
    for t in range(tries):
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            if t == tries-1:
                raise
            time.sleep(2)
