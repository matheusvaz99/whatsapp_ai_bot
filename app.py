""" from fastapi import FastAPI, Request

from message_buffer import buffer_message, redis_client


app = FastAPI()

@app.post('/webhook')
async def webhook(request: Request):
    data = await request.json()
    chat_id = data.get('data').get('key').get('remoteJid')
    message = data.get('data').get('message').get('conversation')
    user_name = data.get('data').get('pushName','Cliente')
    from_me = data.get('data').get('key').get('fromMe', False)

    if from_me:
        source = data.get('data', {}).get('source', '')
        
        if source != 'api':
            pause_key = f"pause:{chat_id}"
            # Define a pausa por 15 minutos (900 segundos)
            await redis_client.set(pause_key, "active", ex=900)

        return {'status': 'ok'}

    message = data.get('message', {}).get('conversation') or \
              data.get('message', {}).get('extendedTextMessage', {}).get('text')
              
    user_name = data.get('pushName', 'Cliente')

    if chat_id and message and not '@g.us' in chat_id:
        await buffer_message(
            chat_id=chat_id,
            message=message,
            user_name=user_name
        )

    return {'status': 'ok'}
 """

from fastapi import FastAPI, Request
import asyncio
from message_buffer import buffer_message, redis_client

app = FastAPI()

@app.post('/webhook')
async def webhook(request: Request):
    try:
        data = await request.json()
        event_data = data.get('data', {})
        key = event_data.get('key', {})
        
        # 1. Prioriza o JID real (evita erro de @lid)
        chat_id = key.get('remoteJidAlt') or key.get('remoteJid')
        from_me = key.get('fromMe', False)
        
        # 2. Captura de texto robusta
        message_obj = event_data.get('message', {})
        message = message_obj.get('conversation') or \
                  message_obj.get('extendedTextMessage', {}).get('text')
        
        # 3. Tratamento para nome nulo
        user_name = event_data.get('pushName') or 'Cliente'

        # --- LOGS DE DEBUG (Aparecerão no seu terminal) ---
        print(f"--- WEBHOOK RECEBIDO ---")
        print(f"Chat: {chat_id} | FromMe: {from_me} | Msg: {message}")

        if from_me:
            source = event_data.get('source', '')
            if source != 'api':
                pause_key = f"pause:{chat_id}"
                await redis_client.set(pause_key, "active", ex=900)
                print(f"[PAUSA] Intervenção humana. Silenciando bot em {chat_id}")
                await redis_client.delete(f"{chat_id}_msg_buffer")
            return {'status': 'ok'}

        # 4. VERIFICAÇÃO FINAL ANTES DE ENVIAR PARA A IA
        if chat_id and message and not '@g.us' in chat_id:
            print(f"[PROCESSANDO] Enviando para o buffer: {user_name} -> {message}")
            asyncio.create_task(
                buffer_message(chat_id, message, user_name)
            )
        else:
            print(f"[IGNORADO] Mensagem vazia ou evento de sistema.")

        return {'status': 'ok'}

    except Exception as e:
        print(f"[ERRO CRÍTICO]: {e}")
        return {'status': 'error'}