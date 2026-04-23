from openai import OpenAI
from config import OPENAI_KEY
import httpx

http_client = httpx.Client()
client = OpenAI(api_key=OPENAI_KEY, http_client=http_client)

STATUS_SYSTEM_PROMPT = (
    'Определи статус лида по полной истории диалога. '
    'Верни только одно слово из списка: согласился, отказался, не ответил. '
    'Если пользователь явно согласен, готов попробовать, просит продолжить или передать дальше — согласился. '
    'Если пользователь явно отказался, не хочет, просит не писать — отказался. '
    'Если нет явного согласия и нет явного отказа, либо пользователь молчит после сообщений бота — не ответил.'
)


def _extract_status(text: str) -> str:
    value = (text or '').strip().lower()
    if 'соглас' in value:
        return 'согласился'
    if 'отказ' in value or 'не интересно' in value or value == 'нет':
        return 'отказался'
    return 'не ответил'


async def analyze_dialog_status(messages: list) -> str:
    try:
        history = '\n'.join(messages[-60:])
        response = client.chat.completions.create(
            model='gpt-4.1-mini',
            messages=[
                {'role': 'system', 'content': STATUS_SYSTEM_PROMPT},
                {'role': 'user', 'content': f'История диалога:\n{history}\n\nСтатус:'}
            ],
            temperature=0,
            max_tokens=10,
        )
        return _extract_status(response.choices[0].message.content or '')
    except Exception as e:
        print(f'❌ Ошибка анализа статуса OpenAI: {e}')
        return 'не ответил'


async def generate_response(messages: list, prompt: str, first_message: str) -> tuple:
    try:
        conversation = prompt + "\n\n"
        if first_message:
            conversation += f"Первое сообщение бота: {first_message}\n\n"
        conversation += "История диалога:\n"
        for msg in messages:
            conversation += f"{msg}\n"

        conversation += "\nТребования к ответу:"
        conversation += "\n- отвечай естественно и кратко;"
        conversation += "\n- учитывай всю историю диалога;"
        conversation += "\n- не повторяй дословно прошлые ответы;"
        conversation += "\n- не пиши длинные полотна текста."
        conversation += "\nСначала сгенерируй следующий ответ пользователю."
        conversation += "\nПосле этого определи статус лида строго одним из значений: согласился / отказался / не ответил."
        conversation += "\nФормат ответа:\nОТВЕТ: <твой ответ>\nСТАТУС: <согласился/отказался/не ответил>"

        response = client.chat.completions.create(
            model='gpt-4.1-mini',
            messages=[
                {'role': 'system', 'content': 'Ты помощник для переписки в Telegram. Пиши кратко, естественно и по делу.'},
                {'role': 'user', 'content': conversation}
            ],
            temperature=0.85,
            max_tokens=500
        )

        result = response.choices[0].message.content or ''
        answer = ''
        status = 'не ответил'

        if 'ОТВЕТ:' in result:
            parts = result.split('ОТВЕТ:', 1)[1].split('СТАТУС:', 1)
            answer = parts[0].strip()
            if len(parts) > 1:
                status = _extract_status(parts[1])
        else:
            answer = result.strip()
            status = await analyze_dialog_status(messages)

        if not answer:
            answer = 'Хорошо. Если хотите, коротко отправлю условия и дальше уже спокойно решите, подходит вам это или нет.'

        return answer, status
    except Exception as e:
        print(f'❌ Ошибка OpenAI: {e}')
        return 'Извините, произошла ошибка. Попробуйте позже.', 'не ответил'


async def generate_followup_response(messages: list, prompt: str, first_message: str = None) -> str:
    try:
        conversation = prompt + "\n\n"
        if first_message:
            conversation += f"Первое сообщение бота в диалоге: {first_message}\n\n"
        conversation += "История диалога:\n"
        for msg in messages:
            conversation += f"{msg}\n"

        conversation += "\nСейчас пользователь не ответил после последнего сообщения бота."
        conversation += "\nНужно сгенерировать одно короткое follow-up сообщение в 1-3 предложения."
        conversation += "\nОтвет верни только текстом сообщения, без пояснений."

        response = client.chat.completions.create(
            model='gpt-4.1-mini',
            messages=[
                {'role': 'system', 'content': 'Ты генерируешь короткие follow-up сообщения для Telegram-переписки. Пиши естественно и коротко.'},
                {'role': 'user', 'content': conversation}
            ],
            temperature=0.75,
            max_tokens=220,
        )

        return (response.choices[0].message.content or '').strip()
    except Exception as e:
        print(f'❌ Ошибка OpenAI follow-up: {e}')
        return 'Подскажите, пожалуйста, актуально ли для вас предложение? Если интересно, коротко сориентирую по дальнейшим шагам.'
