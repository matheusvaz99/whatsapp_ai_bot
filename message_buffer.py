""" import asyncio
import redis.asyncio as redis

from collections import defaultdict

from config import REDIS_URL, BUFFER_KEY_SUFIX, DEBOUNCE_SECONDS, BUFFER_TTL
from evolution_api import send_whatsapp_message
from chains import get_conversational_rag_chain


redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
conversational_rag_chain = get_conversational_rag_chain()
debounce_tasks = defaultdict(asyncio.Task)

def log(*args):
    print('[BUFFER]', *args)


async def buffer_message(chat_id: str, message: str, user_name: str):
    buffer_key = f'{chat_id}{BUFFER_KEY_SUFIX}'

    await redis_client.rpush(buffer_key, message)
    await redis_client.expire(buffer_key, BUFFER_TTL)

    log(f'Mensagem adicionada ao buffer de {chat_id}: {message}')

    if debounce_tasks.get(chat_id):
        debounce_tasks[chat_id].cancel()
        log(f'Debounce resetado para {chat_id}')

    debounce_tasks[chat_id] = asyncio.create_task(handle_debounce(chat_id, user_name))


async def handle_debounce(chat_id: str, user_name: str):
    try:
        log(f'Iniciando debounce para {chat_id}')
        await asyncio.sleep(float(DEBOUNCE_SECONDS))

        if await redis_client.get(f"pause:{chat_id}"):
            return

        buffer_key = f'{chat_id}{BUFFER_KEY_SUFIX}'
        messages = await redis_client.lrange(buffer_key, 0, -1)

        full_message = ' '.join(messages).strip()
        if full_message:
            log(f'Enviando mensagem agrupada para {chat_id}: {full_message}')
            log(f"DEBUG - Nome enviado para a IA: {user_name}")
            ai_response = conversational_rag_chain.invoke(
                input={'input': full_message,
                       'user_name': user_name},
                config={'configurable': {'session_id': chat_id}},
            )['answer']

            send_whatsapp_message(
                number=chat_id,
                text=ai_response,
            )
        await redis_client.delete(buffer_key)

    except asyncio.CancelledError:
        log(f'Debounce cancelado para {chat_id}')
 """

import asyncio
import redis.asyncio as redis
from config import REDIS_URL, BUFFER_KEY_SUFIX, DEBOUNCE_SECONDS, BUFFER_TTL
from evolution_api import send_whatsapp_message
from chains import get_conversational_rag_chain

# Inicialização do Redis e da Chain
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
conversational_rag_chain = get_conversational_rag_chain()

# Usamos um dicionário simples para as tarefas de debounce
debounce_tasks = {}

def log(*args):
    print('[BUFFER]', *args)

async def buffer_message(chat_id: str, message: str, user_name: str):
    try:
        buffer_key = f'{chat_id}{BUFFER_KEY_SUFIX}'

        # Adiciona ao Redis
        await redis_client.rpush(buffer_key, message)
        await redis_client.expire(buffer_key, BUFFER_TTL)

        log(f'Mensagem adicionada ao buffer de {chat_id}: {message}')

        # Gerenciamento do Debounce (Reset se houver tarefa pendente)
        if chat_id in debounce_tasks:
            debounce_tasks[chat_id].cancel()
            log(f'Debounce resetado para {chat_id}')

        # Cria uma nova tarefa para processar após o tempo de espera
        debounce_tasks[chat_id] = asyncio.create_task(handle_debounce(chat_id, user_name))
    
    except Exception as e:
        log(f'ERRO CRÍTICO no buffer_message: {e}')

async def handle_debounce(chat_id: str, user_name: str):
    try:
        log(f'Iniciando espera (debounce) de {DEBOUNCE_SECONDS}s para {chat_id}')
        await asyncio.sleep(float(DEBOUNCE_SECONDS))

        # 1. Checagem de Pausa (Intervenção Humana)
        if await redis_client.get(f"pause:{chat_id}"):
            log(f"Abortando resposta: Intervenção humana ativa para {chat_id}")
            return

        # 2. Recuperação das mensagens agrupadas
        buffer_key = f'{chat_id}{BUFFER_KEY_SUFIX}'
        messages = await redis_client.lrange(buffer_key, 0, -1)
        
        # Limpamos o buffer IMEDIATAMENTE após ler para evitar processamento duplo
        await redis_client.delete(buffer_key)

        full_message = ' '.join(messages).strip()
        
        if full_message:
            log(f'Chamando IA para {chat_id}. Input: {full_message}')
            
            # 3. Chamada ASSÍNCRONA para a OpenAI (ainvoke)
            # Se der erro aqui, agora o try/except vai te avisar!
            response = await conversational_rag_chain.ainvoke(
                input={
                    'input': full_message,
                    'user_name': user_name
                },
                config={'configurable': {'session_id': chat_id}},
            )
            
            ai_response = response['answer']
            log(f'IA respondeu com sucesso para {chat_id}')

            # 4. Envio para o WhatsApp
            send_whatsapp_message(
                number=chat_id,
                text=ai_response,
            )
            log(f'Mensagem enviada via Evolution para {chat_id}')

    except asyncio.CancelledError:
        # Este erro é normal quando o usuário manda várias mensagens rápidas
        pass
    except Exception as e:
        # ESTE LOG É O MAIS IMPORTANTE: Ele vai te dizer se a OpenAI falhou
        log(f'ERRO NO PROCESSAMENTO DA IA para {chat_id}: {e}')
    finally:
        # Limpa a tarefa do dicionário ao finalizar
        if chat_id in debounce_tasks:
            del debounce_tasks[chat_id]