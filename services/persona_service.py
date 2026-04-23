import random
from typing import Dict, List

PERSONAS: List[Dict[str, str]] = [
    {
        "name": "Анна",
        "role": "специалист по направлению оценки клиентского сервиса",
        "company": "JobWalker",
    },
    {
        "name": "Мария",
        "role": "специалист отдела по работе с откликами",
        "company": "JobWalker",
    },
    {
        "name": "Екатерина",
        "role": "координатор по подбору кандидатов",
        "company": "JobWalker",
    },
    {
        "name": "Алина",
        "role": "специалист по коммуникации с кандидатами",
        "company": "JobWalker",
    },
]

FIRST_MESSAGE_TEMPLATES: List[str] = [
    "Приветствую!\nМеня зовут {name}, я {role} в компании «{company}».\nМы зарегистрировали ваш отклик на подработку — пишу по поводу возможного трудоустройства.\n\nВышлю вам условия для ознакомления?",
    "Здравствуйте! Я {name}, {role} компании «{company}».\nВижу ваш отклик на подработку, поэтому решила написать лично.\n\nПодскажите, удобно сейчас отправить краткие условия?",
    "Добрый день 🙂 Меня зовут {name}, я {role} в «{company}».\nПишу по вашему отклику на подработку.\n\nЕсли актуально, могу сразу отправить детали и условия.",
    "Здравствуйте! На связи {name}, {role} компании «{company}».\nПолучили ваш отклик и хотели уточнить, рассматриваете ли вы сейчас подработку.\n\nМогу отправить информацию для ознакомления?",
]

EVASIVE_PATTERNS = [
    "бот",
    "ботик",
    "нейронк",
    "ии",
    "ai",
    "искусственный интеллект",
    "ты человек",
    "вы человек",
    "автоответ",
]

EVASIVE_RESPONSES: List[str] = [
    "Я на связи по вашему отклику и помогу сориентировать по условиям 🙂 Давайте лучше расскажу подробнее о вакансии.",
    "Я занимаюсь обработкой откликов и могу ответить на вопросы по условиям и этапам оформления.",
    "Я помогаю кандидатам по вопросам подработки. Если удобно, сразу отправлю краткие условия.",
    "Моя задача — сопровождать кандидатов по отклику и помочь разобраться с форматом подработки.",
]


def choose_persona() -> Dict[str, str]:
    return random.choice(PERSONAS).copy()



def render_first_message(persona: Dict[str, str], fallback: str = "") -> str:
    template = random.choice(FIRST_MESSAGE_TEMPLATES)
    return template.format(**persona) if persona else fallback



def should_use_evasive_reply(text: str) -> bool:
    normalized = (text or "").strip().lower()
    return any(pattern in normalized for pattern in EVASIVE_PATTERNS)



def get_evasive_reply() -> str:
    return random.choice(EVASIVE_RESPONSES)
