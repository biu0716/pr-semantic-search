from openai import OpenAI

client = OpenAI(
    api_key="sk-0f5875349bd24111b16e5f9d924c9702",
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "user", "content": "你好"}
    ],
)

print(response.choices[0].message.content)