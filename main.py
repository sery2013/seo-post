"""
Автономный SEO-бот для blackbiz.cc
Запускается через GitHub Actions 3 раза в сутки.
Один запуск = один цикл: выбрать раздел → сгенерировать статью → опубликовать в Telegraph.
"""

import io
import os
import re
import json
import math
import base64
import random
import textwrap
import logging
import zipfile
import time
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

# ──────────────────────────────────────────────
# Логирование
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Конфигурация
# ──────────────────────────────────────────────
OPENROUTER_KEY: str = os.getenv("OPENROUTER_KEY", "")
IMGBB_KEY: str      = os.getenv("IMGBB_KEY", "")
FORUM_LINK: str     = "https://blackbiz.cc"

# ──────────────────────────────────────────────
# Пути к файлам
# ──────────────────────────────────────────────
LINKS_FILE   = Path("links.txt")       # лог всех опубликованных ссылок
COUNTER_FILE = Path("counter.txt")     # счётчик текущего раздела (для очерёдности)
COVER_OUTPUT = Path("ready_cover.jpg")
FONT_DIR     = Path("fonts")
FONT_PATH    = FONT_DIR / "Montserrat-Bold.ttf"
BACKGROUND   = Path("background.jpg")

# ──────────────────────────────────────────────
# ВСЕ РАЗДЕЛЫ ФОРУМА
# Формат: (Название раздела, [список SEO-ключей для статей])
# ──────────────────────────────────────────────
SECTIONS: list[tuple[str, list[str]]] = [
    # === Блок 1: Основные ===
    ("Платные методики и курсы", [
        "платные курсы слив", "купить обучение дёшево", "скачать платный курс бесплатно",
        "приватные методики заработка", "закрытые материалы обучение"
    ]),
    ("Бесплатные материалы / База", [
        "бесплатные материалы для заработка", "база знаний фриланс", "скачать бесплатно обучение",
        "бесплатный курс по заработку", "материалы для самообучения бесплатно"
    ]),
    ("Бизнес-идеи / Стартапы", [
        "бизнес идеи 2024", "как открыть стартап с нуля", "идеи для малого бизнеса",
        "стартап идеи без вложений", "бизнес план для начинающих"
    ]),
    ("Стратегии и схемы дохода", [
        "схемы заработка в интернете", "стратегии пассивного дохода", "рабочие схемы заработка",
        "как заработать онлайн схема", "приватные стратегии дохода"
    ]),
    ("Криптоактивы: Airdrop / NFT", [
        "как участвовать в airdrop", "заработок на NFT 2024", "бесплатные токены airdrop",
        "NFT для новичков заработок", "криптоактивы airdrop схема"
    ]),
    ("Черный список / Мошенники", [
        "чёрный список мошенников интернет", "как не попасться на скам", "проверить сайт на мошенничество",
        "мошеннические схемы интернет", "скам проекты список"
    ]),

    # === Блок 2: Обучение ===
    ("SEO / SMM / Арбитраж трафика", [
        "арбитраж трафика с нуля", "SEO продвижение сайта самостоятельно", "SMM заработок в соцсетях",
        "как лить трафик на офферы", "арбитраж трафика схемы 2024"
    ]),
    ("Дизайн / Графика / Видеомонтаж", [
        "обучение дизайну бесплатно", "видеомонтаж для заработка", "графика для фриланса",
        "Photoshop обучение с нуля", "заработок на дизайне"
    ]),
    ("Инвестиции / Криптовалюты", [
        "инвестиции для начинающих 2024", "криптовалюта куда вложить", "пассивный доход инвестиции",
        "как инвестировать с малым капиталом", "криптовалюта инвестиции стратегия"
    ]),
    ("Маркетинг / Реклама / PR", [
        "digital маркетинг для бизнеса", "реклама в интернете бюджет", "PR продвижение бренда",
        "контент маркетинг стратегия", "таргетированная реклама настройка"
    ]),
    ("Здоровье / Фитнес / Спорт", [
        "заработок в сфере фитнес", "онлайн тренер как начать", "продажа курсов по здоровью",
        "фитнес блог монетизация", "спорт бизнес идеи"
    ]),
    ("Гемблинг / Беттинг / Покер", [
        "беттинг стратегия заработка", "покер онлайн обучение", "гемблинг заработок схемы",
        "ставки на спорт стратегия", "покер рум бонусы"
    ]),
    ("Веб-разработка / Сайтостроение", [
        "создание сайта для заработка", "веб разработка фриланс", "сайт на WordPress с нуля",
        "разработка сайтов обучение", "фриланс программирование доход"
    ]),
    ("Программирование / ИИ / Нейросети", [
        "заработок с помощью нейросетей", "ChatGPT для бизнеса", "ИИ инструменты для заработка",
        "программирование для начинающих доход", "нейросети монетизация 2024"
    ]),
    ("Строительство / Ремонт / Дом", [
        "бизнес на ремонте квартир", "строительство как заработать", "услуги ремонта монетизация",
        "бригада ремонт бизнес с нуля", "строительный бизнес идеи"
    ]),
    ("Социальные сети / Видеоплатформы", [
        "монетизация YouTube канала", "заработок в TikTok", "Instagram доход схемы",
        "Telegram канал монетизация", "социальные сети заработок 2024"
    ]),
    ("Туризм / Путешествия / Отдых", [
        "заработок в путешествиях", "travel блог монетизация", "бизнес на туризме онлайн",
        "партнёрки туризм заработок", "путешествия и доход удалённо"
    ]),
    ("Искусство общения / Пикап", [
        "курсы по общению и переговорам", "навыки коммуникации для бизнеса", "обучение продажам через общение",
        "пикап психология отношений", "харизма и влияние на людей"
    ]),
    ("Иностранные языки / Лингвистика", [
        "заработок на знании языков", "переводчик фриланс доход", "обучение английскому для работы",
        "языки удалённая работа", "лингвистика онлайн заработок"
    ]),
    ("Саморазвитие / Психология", [
        "саморазвитие и заработок", "психология успеха в бизнесе", "продуктивность и доход",
        "мышление миллионера книги", "личностный рост монетизация"
    ]),
    ("Бизнес / Стартапы / Управление", [
        "управление бизнесом онлайн", "стартап с нуля до миллиона", "менеджмент малого бизнеса",
        "автоматизация бизнеса доход", "бизнес процессы оптимизация"
    ]),
    ("Имидж / Стиль / Мода", [
        "бизнес на моде и стиле", "стилист онлайн заработок", "продажа одежды в интернете",
        "мода блог монетизация", "имидж консультант доход"
    ]),
    ("Кулинария / Рецепты и гастрономия", [
        "заработок на кулинарии", "food блог монетизация", "кулинарные курсы онлайн продажа",
        "ресторанный бизнес с нуля", "доставка еды бизнес идея"
    ]),
    ("Музыка / Звукорежиссура", [
        "заработок на музыке онлайн", "звукорежиссура фриланс", "продажа битов онлайн",
        "музыкальный бизнес 2024", "монетизация музыки стриминг"
    ]),
    ("Архив книг / Разные материалы", [
        "скачать книги по бизнесу бесплатно", "архив бизнес литературы", "книги по заработку список",
        "лучшие книги для предпринимателя", "бизнес книги бесплатно скачать"
    ]),
    ("Эзотерика / Самопознание", [
        "эзотерика заработок онлайн", "нумерология бизнес", "таро гадание заработок",
        "астрология монетизация", "эзотерика для привлечения денег"
    ]),

    # === Блок 3: Виды заработка ===
    ("Форекс / Трейдинг / ПАММ-счета", [
        "форекс трейдинг для начинающих", "ПАММ счета инвестиции", "торговля на форекс стратегия",
        "трейдинг обучение с нуля", "как заработать на форекс"
    ]),
    ("Криптовалюты / Web3", [
        "криптовалюта заработок 2024", "Web3 проекты для заработка", "DeFi пассивный доход",
        "как заработать на крипте", "Bitcoin Ethereum инвестиции"
    ]),
    ("Гемблинг / Казино / Слоты", [
        "казино онлайн стратегии", "слоты с бонусами без депозита", "партнёрка казино заработок",
        "гемблинг бизнес арбитраж", "онлайн казино схемы"
    ]),
    ("Инвестиционные фонды / HYIP", [
        "HYIP инвестиции риски", "инвестиционные фонды онлайн", "пассивный доход фонды",
        "как выбрать HYIP проект", "инвестиции в фонды стратегия"
    ]),
    ("Сетевой маркетинг / МЛМ", [
        "МЛМ бизнес как заработать", "сетевой маркетинг схема", "MLM компании рейтинг",
        "сетевой бизнес с нуля", "пассивный доход МЛМ"
    ]),
    ("Экономические игры с выводом", [
        "игры с выводом денег 2024", "P2E игры заработок", "экономические игры реальный вывод",
        "play to earn крипто игры", "игры на телефоне с выводом"
    ]),
    ("Альтернативный доход", [
        "альтернативные источники дохода", "пассивный доход идеи 2024", "нестандартные схемы заработка",
        "доход без вложений схемы", "несколько источников дохода"
    ]),
    ("Партнерские сети / CPA", [
        "CPA партнёрки заработок", "партнёрские программы топ 2024", "арбитраж CPA сети",
        "как заработать на партнёрках", "CPA маркетинг с нуля"
    ]),
]

# Цвета иконок по группам
SECTION_COLORS: dict[str, tuple] = {
    "Платные методики и курсы":          ((124, 58, 237),  "₽"),
    "Бесплатные материалы / База":       ((16, 185, 129),  "📚"),
    "Бизнес-идеи / Стартапы":           ((245, 158, 11),  "💡"),
    "Стратегии и схемы дохода":          ((239, 68, 68),   "$"),
    "Криптоактивы: Airdrop / NFT":       ((99, 102, 241),  "◈"),
    "Черный список / Мошенники":         ((107, 114, 128), "✗"),
    "SEO / SMM / Арбитраж трафика":      ((59, 130, 246),  "↗"),
    "Дизайн / Графика / Видеомонтаж":    ((236, 72, 153),  "✦"),
    "Инвестиции / Криптовалюты":         ((234, 179, 8),   "₿"),
    "Маркетинг / Реклама / PR":          ((20, 184, 166),  "📣"),
    "Здоровье / Фитнес / Спорт":         ((34, 197, 94),   "♥"),
    "Гемблинг / Беттинг / Покер":        ((239, 68, 68),   "♠"),
    "Веб-разработка / Сайтостроение":    ((99, 102, 241),  "</>"),
    "Программирование / ИИ / Нейросети": ((139, 92, 246),  "AI"),
    "Строительство / Ремонт / Дом":      ((180, 83, 9),    "🏠"),
    "Социальные сети / Видеоплатформы":  ((59, 130, 246),  "▶"),
    "Туризм / Путешествия / Отдых":      ((16, 185, 129),  "✈"),
    "Искусство общения / Пикап":         ((236, 72, 153),  "♟"),
    "Иностранные языки / Лингвистика":   ((245, 158, 11),  "A"),
    "Саморазвитие / Психология":         ((139, 92, 246),  "∞"),
    "Бизнес / Стартапы / Управление":    ((239, 68, 68),   "B"),
    "Имидж / Стиль / Мода":             ((236, 72, 153),  "★"),
    "Кулинария / Рецепты и гастрономия": ((245, 158, 11),  "♨"),
    "Музыка / Звукорежиссура":           ((99, 102, 241),  "♪"),
    "Архив книг / Разные материалы":     ((107, 114, 128), "≡"),
    "Эзотерика / Самопознание":          ((139, 92, 246),  "✧"),
    "Форекс / Трейдинг / ПАММ-счета":   ((34, 197, 94),   "📈"),
    "Криптовалюты / Web3":              ((234, 179, 8),   "⬡"),
    "Гемблинг / Казино / Слоты":        ((239, 68, 68),   "7"),
    "Инвестиционные фонды / HYIP":      ((16, 185, 129),  "%"),
    "Сетевой маркетинг / МЛМ":          ((59, 130, 246),  "◎"),
    "Экономические игры с выводом":     ((245, 158, 11),  "🎮"),
    "Альтернативный доход":             ((20, 184, 166),  "+"),
    "Партнерские сети / CPA":           ((124, 58, 237),  "CPA"),
}
DEFAULT_COLOR = ((60, 60, 80), "•")


# ══════════════════════════════════════════════
# ОЧЕРЁДНОСТЬ РАЗДЕЛОВ
# ══════════════════════════════════════════════

def get_next_section() -> tuple[str, list[str]]:
    """
    Возвращает следующий раздел по кругу.
    Текущий индекс хранится в counter.txt и коммитится в репо.
    """
    total = len(SECTIONS)
    if COUNTER_FILE.exists():
        try:
            idx = int(COUNTER_FILE.read_text().strip()) % total
        except ValueError:
            idx = 0
    else:
        idx = 0

    section_name, keywords = SECTIONS[idx]
    next_idx = (idx + 1) % total
    COUNTER_FILE.write_text(str(next_idx))

    log.info("Раздел [%d/%d]: «%s»", idx + 1, total, section_name)
    return section_name, keywords


# ══════════════════════════════════════════════
# ШРИФТ: авто-загрузка
# ══════════════════════════════════════════════

MONTSERRAT_ZIP_URL = "https://github.com/JulietaUla/Montserrat/archive/refs/heads/master.zip"
FONT_INSIDE_ZIP    = "Montserrat-master/fonts/ttf/Montserrat-Bold.ttf"


def ensure_font() -> Path:
    if FONT_PATH.exists():
        return FONT_PATH
    log.info("Скачиваю шрифт Montserrat-Bold…")
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(MONTSERRAT_ZIP_URL, timeout=60)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            entry = FONT_INSIDE_ZIP if FONT_INSIDE_ZIP in zf.namelist() \
                    else next((n for n in zf.namelist() if "Bold" in n and n.endswith(".ttf")), None)
            if not entry:
                raise RuntimeError("Bold TTF не найден в ZIP")
            FONT_PATH.write_bytes(zf.read(entry))
        log.info("Шрифт сохранён: %s", FONT_PATH)
    except Exception as exc:
        log.warning("Не удалось скачать шрифт: %s", exc)
        for sys_path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]:
            if Path(sys_path).exists():
                return Path(sys_path)
    return FONT_PATH


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    p = ensure_font()
    if p and p.exists():
        return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


# ══════════════════════════════════════════════
# ИКОНКА: программная генерация
# ══════════════════════════════════════════════

def generate_icon(section_name: str, size: int = 160) -> Image.Image:
    color, symbol = SECTION_COLORS.get(section_name, DEFAULT_COLOR)
    canvas = size + 20
    img  = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Тень
    draw.ellipse([16, 16, size + 16, size + 16], fill=(0, 0, 0, 70))
    # Круг
    draw.ellipse([10, 10, size + 10, size + 10], fill=(*color, 255))
    # Символ
    fsize = max(int(size * 0.36), 14)
    font  = _font(fsize)
    bbox  = draw.textbbox((0, 0), symbol, font=font)
    tx = (canvas - (bbox[2] - bbox[0])) // 2 - bbox[0]
    ty = (canvas - (bbox[3] - bbox[1])) // 2 - bbox[1]
    draw.text((tx, ty), symbol, font=font, fill=(255, 255, 255, 255))
    return img.crop((0, 0, size, size))


# ══════════════════════════════════════════════
# ШАГ 1: Генерация статьи через OpenRouter
# ══════════════════════════════════════════════

def generate_article(section: str, keywords: list[str]) -> dict:
    """
    Запрашивает у DeepSeek статью 2000-2500 символов по разделу форума.
    Ключи вшиваются в заголовок и текст органично.
    Возвращает dict: title, cover_words, text, anchor
    """
    kw_str = ", ".join(keywords)

    prompt = f"""Ты — опытный SEO-копирайтер для русскоязычного форума по интернет-заработку blackbiz.cc.

Напиши статью для раздела форума: «{section}»

SEO-ключевые слова (использовать органично в заголовке и тексте): {kw_str}

Требования к статье:
1. Заголовок — кликабельный, содержит 1-2 ключевых слова, до 70 символов, без кликбейта.
2. Объём текста — строго 3000-3500 символов (считая пробелы). Это важно.
3. Структура текста — используй следующие специальные теги форматирования:

   [h3]Текст подзаголовка[/h3] — для заголовков разделов (2-3 штуки в статье)
   [b]важное слово или фраза[/b] — для жирного выделения ключевых слов (5-8 раз в тексте)
   [ul]
   [li]пункт списка[/li]
   [li]пункт списка[/li]
   [/ul] — для маркированных списков (1-2 списка в статье, 3-5 пунктов каждый)

   Разделяй абзацы пустой строкой (\\n\\n).

4. Ключевые слова из списка вписать в текст естественно, не спамить.
5. В предпоследнем абзаце ОБЯЗАТЕЛЬНО упомяни форум — используй тег: FORUM_ANCHOR (оставь именно этот тег, не заменяй его).
6. Тон — экспертный, живой, без воды. Пиши как практик.
7. cover_words — 3-4 самых важных слова из заголовка для обложки (короткая фраза).

Пример структуры текста:
Вступительный абзац с [b]ключевым словом[/b] и общим контекстом.\\n\\n[h3]Первый подзаголовок[/h3]\\n\\nТекст абзаца...\\n\\n[ul]\\n[li]Первый пункт[/li]\\n[li]Второй пункт[/li]\\n[/ul]\\n\\n[h3]Второй подзаголовок[/h3]\\n\\nТекст с FORUM_ANCHOR в предпоследнем абзаце.\\n\\nЗаключение.

Ответь ТОЛЬКО валидным JSON без markdown-обёрток. Структура:
{{"title": "...", "cover_words": "...", "text": "..."}}"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": FORUM_LINK,
        "X-Title": "BlackBiz SEO Bot",
    }
    payload = {
        "model": "deepseek/deepseek-chat",
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
    }

    log.info("Запрос к OpenRouter…")
    raw = None
    for attempt in range(1, 4):  # 3 попытки
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=payload, timeout=90,
            )
            if resp.status_code == 429:
                wait = 30 * attempt
                log.warning("429 Too Many Requests. Жду %d сек (попытка %d/3)…", wait, attempt)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            break
        except requests.RequestException as exc:
            if attempt == 3:
                raise RuntimeError(f"OpenRouter недоступен после 3 попыток: {exc}") from exc
            log.warning("Ошибка запроса (попытка %d/3): %s", attempt, exc)
            time.sleep(15)

    if raw is None:
        raise RuntimeError("OpenRouter не вернул ответ после 3 попыток (429). Пополни баланс на openrouter.ai")
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1].lstrip("json").strip() if len(parts) >= 2 else raw

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Не удалось разобрать JSON: {exc}\n{raw}") from exc

    for key in ("title", "cover_words", "text"):
        if key not in data:
            raise RuntimeError(f"Нет ключа «{key}» в ответе AI")

    char_count = len(data["text"])
    log.info("Статья: «%s» (%d симв.)", data["title"], char_count)

    # Если текст слишком короткий — просим дописать
    if char_count < 2500:
        log.warning("Текст короткий (%d симв.), запрашиваю продолжение…", char_count)
        extend_payload = {
            "model": "deepseek/deepseek-chat",
            "max_tokens": 2000,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                    f"Текст статьи получился слишком коротким ({char_count} символов). "
                    "Дополни его ещё на 1500-2000 символов: добавь ещё один раздел [h3] с подзаголовком, "
                    "маркированный список [ul][li] и развёрнутый абзац. "
                    "Верни ТОЛЬКО обновлённый JSON с тем же форматом, где поле text содержит ПОЛНЫЙ текст статьи (старый + новый)."
                )},
            ],
        }
        try:
            resp2 = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=extend_payload, timeout=90,
            )
            resp2.raise_for_status()
            raw2 = resp2.json()["choices"][0]["message"]["content"].strip()
            if raw2.startswith("```"):
                parts2 = raw2.split("```")
                raw2 = parts2[1].lstrip("json").strip() if len(parts2) >= 2 else raw2
            data2 = json.loads(raw2)
            if "text" in data2 and len(data2["text"]) > char_count:
                data["text"] = data2["text"]
                log.info("Текст дополнен: %d симв.", len(data["text"]))
        except Exception as exc:
            log.warning("Не удалось дополнить текст: %s. Публикую как есть.", exc)

    return data


# ══════════════════════════════════════════════
# ШАГ 2: Генерация обложки
# ══════════════════════════════════════════════

def _gradient_bg() -> Image.Image:
    img  = Image.new("RGB", (1200, 630))
    draw = ImageDraw.Draw(img)
    for y in range(630):
        t = y / 630
        draw.line([(0, y), (1200, y)], fill=(
            int(15 + 20 * (1 - t)),
            int(15 + 25 * (1 - t)),
            int(35 + 45 * (1 - t)),
        ))
    return img


def create_cover(cover_words: str, section: str) -> Path:
    # Фон
    if BACKGROUND.exists():
        bg = Image.open(BACKGROUND).convert("RGB").resize((1200, 630), Image.LANCZOS)
    else:
        bg = _gradient_bg()

    overlay = Image.new("RGBA", (1200, 630), (0, 0, 0, 110))
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(bg)

    # Иконка
    icon = generate_icon(section, 160)
    bg.paste(icon, ((1200 - 160) // 2, 70), mask=icon)

    # Текст
    font = _font(54)
    lines = textwrap.wrap(cover_words, width=16)
    y = 268
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (1200 - w) // 2
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 150))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += (bbox[3] - bbox[1]) + 16

    bg.save(COVER_OUTPUT, "JPEG", quality=92)
    log.info("Обложка готова: %s", COVER_OUTPUT)
    return COVER_OUTPUT


# ══════════════════════════════════════════════
# ШАГ 3: Загрузка на ImgBB
# ══════════════════════════════════════════════

def upload_to_imgbb(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    log.info("Загружаю обложку на ImgBB…")
    try:
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            params={"key": IMGBB_KEY},
            data={"image": b64},
            timeout=60,
        )
        log.info("ImgBB статус: %d", resp.status_code)
        if resp.status_code != 200:
            log.error("ImgBB ответ: %s", resp.text[:300])
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"ImgBB недоступен: {exc}") from exc

    result = resp.json()
    if not result.get("success"):
        raise RuntimeError(f"ImgBB ошибка: {result}")
    url = result["data"]["url"]
    log.info("Обложка: %s", url)
    try:
        path.unlink()
    except OSError:
        pass
    return url


# ══════════════════════════════════════════════
# ШАГ 4: Публикация в Telegraph
# ══════════════════════════════════════════════

def _get_telegraph_token() -> str:
    resp = requests.get(
        "https://api.telegra.ph/createAccount",
        params={"short_name": "BlackBizBot", "author_name": "BlackBiz.cc"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegraph createAccount: {data}")
    return data["result"]["access_token"]


def _parse_inline(text: str) -> list:
    """
    Парсит inline-теги внутри абзаца:
      [b]...[/b]   → {"tag": "b", "children": [...]}
      FORUM_ANCHOR → {"tag": "a", ...}
    Возвращает список строк и node-объектов.
    """
    anchor_node = {
        "tag": "a",
        "attrs": {"href": FORUM_LINK},
        "children": ["форуме BlackBiz.cc"],
    }

    # Сначала заменяем FORUM_ANCHOR на плейсхолдер чтобы не конфликтовал с regex
    text = text.replace("FORUM_ANCHOR", "\x00ANCHOR\x00")

    result = []
    # Ищем [b]...[/b]
    pattern = re.compile(r'\[b\](.*?)\[/b\]', re.DOTALL)
    last = 0
    for m in pattern.finditer(text):
        before = text[last:m.start()]
        if before:
            # Разбиваем before по ANCHOR
            for chunk in before.split("\x00ANCHOR\x00"):
                if chunk:
                    result.append(chunk)
                result.append(anchor_node)
            result.pop()  # убираем лишний anchor_node в конце
        result.append({"tag": "b", "children": [m.group(1)]})
        last = m.end()

    tail = text[last:]
    if tail:
        for chunk in tail.split("\x00ANCHOR\x00"):
            if chunk:
                result.append(chunk)
            result.append(anchor_node)
        result.pop()

    # Убираем пустые строки из результата
    result = [r for r in result if r != ""]
    return result if result else [text.replace("\x00ANCHOR\x00", "")]


def _build_content(text: str, image_url: str) -> list[dict]:
    """
    Строит Node-массив для Telegraph из текста с тегами:
      [h3]...[/h3]     → подзаголовок h3
      [b]...[/b]       → жирный текст
      [ul][li]...[/ul] → маркированный список
      FORUM_ANCHOR     → ссылка на форум
    """
    nodes: list[dict] = [{"tag": "img", "attrs": {"src": image_url}}]

    # Нормализуем переносы строк
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Разбиваем на блоки по двойному переносу
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]

    for block in blocks:

        # — Подзаголовок h3 —
        h3_match = re.match(r'^\[h3\](.*?)\[/h3\]$', block, re.DOTALL)
        if h3_match:
            nodes.append({"tag": "h3", "children": [h3_match.group(1).strip()]})
            continue

        # — Маркированный список —
        if "[ul]" in block:
            items = re.findall(r'\[li\](.*?)\[/li\]', block, re.DOTALL)
            if items:
                li_nodes = [
                    {"tag": "li", "children": _parse_inline(item.strip())}
                    for item in items
                ]
                nodes.append({"tag": "ul", "children": li_nodes})
                continue

        # — Обычный абзац (с inline-форматированием) —
        children = _parse_inline(block)
        if children:
            nodes.append({"tag": "p", "children": children})

    return nodes


def publish_to_telegraph(title: str, text: str, image_url: str) -> str:
    token   = _get_telegraph_token()
    content = _build_content(text, image_url)

    log.info("Публикую в Telegraph…")
    try:
        resp = requests.post(
            "https://api.telegra.ph/createPage",
            data={
                "access_token": token,
                "title": title,
                "content": json.dumps(content, ensure_ascii=False),
                "return_content": "false",
            },
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Telegraph createPage: {exc}") from exc

    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegraph ошибка: {result}")
    return result["result"]["url"]


# ══════════════════════════════════════════════
# ШАГ 5: Сохранение ссылки и статьи
# ══════════════════════════════════════════════

def save_link(section: str, title: str, page_url: str, text: str) -> None:
    """
    Дописывает запись в links.txt:
    дата | раздел | заголовок | ссылка
    """
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    line = f"[{now}] [{section}] {title} → {page_url}\n"
    with open(LINKS_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    log.info("Ссылка сохранена в %s", LINKS_FILE)


# ══════════════════════════════════════════════
# Проверка окружения
# ══════════════════════════════════════════════

def _check_env() -> None:
    missing = [k for k, v in [("OPENROUTER_KEY", OPENROUTER_KEY), ("IMGBB_KEY", IMGBB_KEY)] if not v]
    if missing:
        raise EnvironmentError(f"Не заданы переменные окружения: {', '.join(missing)}")


# ══════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════

def main() -> None:
    log.info("═" * 55)
    log.info("BlackBiz SEO-бот запущен")
    log.info("═" * 55)

    _check_env()

    # 1. Следующий раздел по очереди
    section, keywords = get_next_section()

    # 2. Генерация статьи
    try:
        article = generate_article(section, keywords)
    except RuntimeError as exc:
        log.error("Ошибка генерации: %s", exc)
        return

    title       = article["title"]
    cover_words = article["cover_words"]
    text        = article["text"]

    # 3. Обложка
    try:
        cover_path = create_cover(cover_words, section)
    except Exception as exc:
        log.error("Ошибка обложки: %s", exc)
        return

    # 4. ImgBB
    try:
        image_url = upload_to_imgbb(cover_path)
    except RuntimeError as exc:
        log.error("Ошибка ImgBB: %s", exc)
        return

    # 5. Telegraph
    try:
        page_url = publish_to_telegraph(title, text, image_url)
    except RuntimeError as exc:
        log.error("Ошибка Telegraph: %s", exc)
        return

    # 6. Сохранить ссылку
    save_link(section, title, page_url, text)

    log.info("═" * 55)
    log.info("✅  Опубликовано!")
    log.info("    Раздел  : %s", section)
    log.info("    Заголовок: %s", title)
    log.info("    Ссылка  : %s", page_url)
    log.info("═" * 55)


if __name__ == "__main__":
    main()
