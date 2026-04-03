from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from config import (
    AI_CONTEXTUALIZE_PROMPT,
    AI_SYSTEM_PROMPT,
)


contextualize_prompt = ChatPromptTemplate.from_messages([
    ('system', AI_CONTEXTUALIZE_PROMPT+ "\n\nO nome do usuário é: {user_name}"),
    MessagesPlaceholder('chat_history'),
    ('human', '{input}'),
])

qa_prompt = ChatPromptTemplate.from_messages([
    ('system', AI_SYSTEM_PROMPT),
    MessagesPlaceholder('chat_history'),
    ('human', '{input}'),
]).partial(user_name="Cliente")
