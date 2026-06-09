"""
⚽ SoccerPaperwork Bot — для Render.com
Керуєш з телефону через Telegram.
"""

import os, requests, feedparser, logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════
# КОНФІГ — вставляєш в Render як Environment Variables
# ══════════════════════════════════════════════

TOKEN = os.environ.get("BOT_TOKEN", "")
PORT  = int(os.environ.get("PORT", 8080))  # Render вимагає веб-порт

WC_API  = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

FAVORITES = {
    "France","Spain","England","Brazil","Argentina",
    "Portugal","Germany","Netherlands"
}

PLAYERS = {
    # Англія
    "Bukayo Saka":        "England",  "Harry Kane":         "England",
    "Phil Foden":         "England",  "Cole Palmer":        "England",
    "Jude Bellingham":    "England",  "Marcus Rashford":    "England",
    "Declan Rice":        "England",  "Harry Maguire":      "England",
    "Ivan Toney":         "England",  "Ollie Watkins":      "England",
    # Франція
    "Kylian Mbappe":      "France",   "Antoine Griezmann":  "France",
    "Ousmane Dembele":    "France",   "Theo Hernandez":     "France",
    # Іспанія
    "Pedri":              "Spain",    "Lamine Yamal":       "Spain",
    "Ferran Torres":      "Spain",    "Dani Olmo":          "Spain",
    # Португалія
    "Bruno Fernandes":    "Portugal", "Cristiano Ronaldo":  "Portugal",
    "Rafael Leao":        "Portugal", "Joao Felix":         "Portugal",
    # Аргентина
    "Lionel Messi":       "Argentina","Lautaro Martinez":   "Argentina",
    "Federico Valverde":  "Argentina","Julian Alvarez":     "Argentina",
    # Бразилія
    "Vinicius Junior":    "Brazil",   "Rodrygo":            "Brazil",
    "Richarlison":        "Brazil",   "Gabriel Martinelli": "Brazil",
    # Інші фаворити
    "Erling Haaland":     "Norway",   "Cody Gakpo":         "Netherlands",
    "Memphis Depay":      "Netherlands","Wout Weghorst":    "Netherlands",
    "Florian Wirtz":      "Germany",  "Jamal Musiala":      "Germany",
    "Leroy Sane":         "Germany",  "Robert Lewandowski": "Poland",
    "Dusan Vlahovic":     "Serbia",   "Son Heung-min":      "South Korea",
    "Achraf Hakimi":      "Morocco",  "Christian Pulisic":  "USA",
    "Gio Reyna":          "USA",      "Alphonso Davies":    "Canada",
    "Hirving Lozano":     "Mexico",
    # Прізвища — ЗМІ часто пишуть без імені
    "Messi":              "Argentina", "Mbappe":            "France",
    "Ronaldo":            "Portugal",  "Kane":              "England",
    "Saka":               "England",   "Bellingham":        "England",
    "Foden":              "England",   "Haaland":           "Norway",
    "Lewandowski":        "Poland",    "Musiala":           "Germany",
    "Vinicius":           "Brazil",    "Pulisic":           "USA",
    "Hakimi":             "Morocco",   "Davies":            "Canada",
    "Valverde":           "Argentina", "Alvarez":           "Argentina",
    "Yamal":              "Spain",     "Gakpo":             "Netherlands",
    "Wirtz":              "Germany",   "Son":               "South Korea",
    "Lozano":             "Mexico",    "Leao":              "Portugal",
    "Dembele":            "France",    "Griezmann":         "France",
    "Pedri":              "Spain",     "Olmo":              "Spain",
}

TEAMS_BANDWAGON = [
    # Фаворити — якщо вилітають = максимальний вибух
    "France","Spain","England","Brazil","Argentina","Portugal",
    "Germany","Netherlands","Belgium","Croatia","Uruguay",
    # Середняки
    "USA","Mexico","Canada","Morocco","Senegal","South Korea",
    "Japan","Poland","Serbia","Switzerland","Denmark","Ecuador",
    # Аутсайдери — майже гарантований вильот в групі
    "Saudi Arabia","Iran","Australia","Cameroon","Ghana",
    "Tunisia","Costa Rica","Qatar","New Zealand","South Africa",
    "Czech Republic","Wales",
]

RSS_FEEDS = {
    "BBC Sport":  "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "Goal.com":   "https://www.goal.com/feeds/en/news",
    "ESPN FC":    "https://www.espn.com/espn/rss/soccer/news",
    "Sky Sports": "https://www.skysports.com/rss/12040",
    "90min":      "https://www.90min.com/feed",
    "r/soccer":   "https://www.reddit.com/r/soccer/top/.rss?t=day",
    "r/worldcup": "https://www.reddit.com/r/worldcup/top/.rss?t=day",
}

KW = {
    "apology": [
        # Конкретні дії гравця (факти, не епітети)
        "scores","scored","goal","winner","saves","assist",
        "bicycle kick","free kick","hat trick","brace",
        "wonder goal","man of the match","penalty scored",
        "free kick goal","overhead kick","volley",
        "rescues","advance","through","wins","victory",
        # Реакція фанатів і медіа
        "apology","proved","silenced","haters","critics",
        "underrated","comeback","world class","redemption",
        "goat","hero","player of the tournament",
        # Командні результати з позитивом
        "qualify","qualified","semi-final","final","champion",
        "through to","progress","advance to",
    ],
    "bandwagon": [
        # Вильоти і поразки
        "eliminated","knocked out","exit","group stage","early exit",
        "shocking","upset","go home","crashed out","heartbreak",
        "out of world cup","shock result","giant killing",
        "bow out","dumped out","beaten","defeated","suffer defeat",
        "dream over","penalties","penalty shootout",
        "quarterfinal exit","round of 16","last 16 exit",
        "stunning defeat","narrow defeat","shock defeat","sent home",
        "farewell","tournament over","final whistle",
        "crash out","crashes out","out of","fall to","fall at",
    ],
    "var": [
        # Класичні VAR
        "VAR","offside","disallowed","controversy","robbery","referee",
        "penalty denied","wrong decision","overturned","injustice",
        "robbed","scandalous","outrage","red card","video review",
        "not given","disputed","howler","blunder",
        # VAR інциденти
        "handball","linesman","flag","ruled out","goal ruled",
        "goal disallowed","furious fans","fans furious",
        "banned","horror show","slams referee","under fire",
        "minimal contact","soft penalty","dubious","questionable",
        "shocking decision","disgraceful","embarrassing",
        "appeal","protest","complains","complaint",
        "goal-line","clear error","human error",
        "wrong call","missed call","poor decision",
    ],
}

# Gumroad посилання — замінити своїми після публікації
GUMROAD = {
    "bandwagon": "https://gumroad.com/l/BANDWAGON",
    "apology":   "https://gumroad.com/l/APOLOGY",
    "var":       "https://gumroad.com/l/VAR",
    "foulplay":  "https://gumroad.com/l/FOULPLAY",
    "bundle":    "https://gumroad.com/l/BUNDLE",
}

HOOKS = {
    "var": (
        "🔴 *VAR HOOK — постити ЗАРАЗ:*\n\n"
        "```\nVAR = Video Assisted Robbery.\n"
        "If your team got robbed tonight —\n"
        "you deserve official documentation.\n"
        "Comment ROBBERY and I'll DM it 👇\n"
        "[VAR Robbery Certificate — $2.99]```"
    ),
    "bandwagon": (
        "🟡 *BANDWAGON HOOK — постити ЗАРАЗ:*\n\n"
        "```\n[Team] fans right now searching\n"
        "for a new team to support...\n"
        "Time to make it official.\n"
        "Comment FORM and I'll DM it 👇\n"
        "[Bandwagon Fan Application — $1.99]```"
    ),
    "apology": (
        "🟢 *APOLOGY HOOK — постити ЗАРАЗ:*\n\n"
        "```\nEveryone who said [Player] was\n"
        "finished needs to fill this out.\n"
        "Right now. In public.\n"
        "Comment APOLOGY and I'll DM it 👇\n"
        "[Formal Apology Form — $1.99]```"
    ),
    "foulplay": (
        "🟠 *FOUL PLAY HOOK — завжди актуальний:*\n\n"
        "```\nHalf your friends don't understand\n"
        "soccer. Good. FOUL PLAY rewards\n"
        "exactly that.\n"
        "Comment GAME and I'll DM it 👇\n"
        "[FOUL PLAY Watch Party Game — $4.99]```"
    ),
}

# ══════════════════════════════════════════════
# ВЕБ-СЕРВЕР (щоб Render не вимикав бота)
# ══════════════════════════════════════════════

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"SoccerPaperwork Bot is alive!")
    def log_message(self, *args):
        pass  # вимикаємо зайві логи

def run_web_server():
    server = HTTPServer(("0.0.0.0", PORT), KeepAliveHandler)
    server.serve_forever()

# ══════════════════════════════════════════════
# ЛОГІКА АНАЛІЗУ
# ══════════════════════════════════════════════

# Стоп-слова — якщо є, це не матчева новина (не тригерить продажі)
STOP_WORDS = [
    # Нефутбольний контент
    "cannes","oscar","grammy","stock market","election","politician",
    "hospital","medical","surgery","film festival","movie","cinema",
    "album","concert","fashion","startup","funding round",
    # Трансфери і контракти
    "transfer","bid","rejected","linked with","loan","contract",
    "signing","signed","fee","million pound","release clause",
    "interested in","move to","join","left the club","departure",
    "rumour","rumor","saga","negotiations","talks",
    # Клубний футбол і комерція (не ЧС контент)
    "kit","shirt","jersey","sponsor","sponsorship",
    "premier league","champions league","la liga","serie a",
    "bundesliga","ligue 1","eredivisie","mls cup",
    "debut","medical","salary","wage","buyout",
    # Загальні анонси без матчу
    "squad announced","named in squad","injury concern",
    "fitness doubt","press conference","prediction",
    "retirement","farewell","legacy","career",
    "interview","speaks out","breaks silence","opens up",
    "ranked","ranking","best xi","top 10","history of",
    "preview","what to watch","things to know",
]

# Футбольні контекст-слова — хоча б одне має бути присутнє
FOOTBALL_CONTEXT = [
    "football","soccer","world cup","match","goal","player","team",
    "squad","stadium","pitch","league","tournament","fifa","uefa",
    "penalty","referee","offside","transfer","manager","coach",
    "england","france","spain","brazil","argentina","germany",
    "portugal","netherlands","usa","mexico","morocco","japan",
]

def score_text(title, summary=""):
    # ФІКС 4: аналізуємо заголовок і summary окремо
    # Збіг у заголовку = вдвічі важливіший
    t_title   = title.lower()
    t_summary = summary.lower() if summary else ""
    t         = t_title + " " + t_summary  # повний текст для стоп-слів

    # Стоп-фільтр — нефутбольний / клубний контент
    for stop in STOP_WORDS:
        if stop in t:
            return "apology", 0, [], []

    # Контекст-фільтр — хоча б одне футбольне слово
    has_football_context = any(fw in t for fw in FOOTBALL_CONTEXT)

    scores = {"apology": 0, "bandwagon": 0, "var": 0}
    found_players, found_teams = [], []

    for player in PLAYERS:
        pl = player.lower()
        if pl in t_title:
            scores["apology"] += 4   # в заголовку = х2 вага
            found_players.append(player)
        elif pl in t_summary:
            scores["apology"] += 2   # в summary = стандартна вага

    for team in TEAMS_BANDWAGON:
        tm = team.lower()
        if tm in t_title:
            for kw in KW["bandwagon"]:
                if kw in t_title:
                    scores["bandwagon"] += 4  # заголовок = х2
                    found_teams.append(team)
                    break
            else:
                # Команда в заголовку без бандвагон-слова — перевіряємо summary
                for kw in KW["bandwagon"]:
                    if kw in t_summary:
                        scores["bandwagon"] += 2
                        found_teams.append(team)
                        break
        elif tm in t_summary:
            for kw in KW["bandwagon"]:
                if kw in t_summary:
                    scores["bandwagon"] += 2
                    found_teams.append(team)
                    break

    # KW scoring: заголовок = +2, summary = +1
    for kw_type, kws in KW.items():
        for kw in kws:
            kw_l = kw.lower()
            if kw_l in t_title:
                scores[kw_type] += 2
            elif kw_l in t_summary:
                scores[kw_type] += 1

    best  = max(scores, key=scores.get)
    total = scores[best]

    # ACTION WORDS — конкретні події на полі
    ACTION_WORDS = [
        "scores","scored","goal","wins","winner","advance","through",
        "eliminated","knocked out","exit","crashed out","beaten",
        "VAR","disallowed","robbery","outrage","penalty","red card",
        "hat trick","brace","hero","qualify","semi-final","final",
        "bicycle kick","free kick","overhead kick","wonder goal",
    ]
    has_action = any(aw in t for aw in ACTION_WORDS)

    # World Cup Entity Rule:
    # Якщо немає конкретного гравця/команди І немає прямої згадки ЧС — ігноруємо
    is_world_cup_direct = any(w in t for w in [
        "world cup","fifa","wc2026","wc 2026","tournament",
        "group stage","knockout","round of","quarter","semi-final",
    ])
    has_entity = len(found_players) > 0 or len(found_teams) > 0

    # VAR/скандальний контент не завжди містить "world cup" в заголовку
    var_score = scores.get("var", 0)
    is_var_incident = var_score >= 2  # мінімум 2 VAR тригери = достатньо

    if not has_entity and not is_world_cup_direct and not is_var_incident:
        return best, 0, [], []

    # Гравець без дії = не тригер (трансфери, інтерв'ю)
    if found_players and not has_action and not found_teams:
        return best, 0, found_players, found_teams

    # Команда або World Cup згадка = контекст підтверджений
    if found_teams or is_world_cup_direct:
        has_football_context = True

    if not has_football_context and total < 3:
        return best, 0, found_players, found_teams

    return best, total, found_players, found_teams


def fetch_matches():
    try:
        r = requests.get(WC_API, timeout=10, headers=HEADERS)
        data = r.json()
        matches  = data.get("matches", [])
        today    = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        played  = [m for m in matches if m.get("score")]
        today_m = [m for m in matches if m.get("date") == today]
        tomrw_m = [m for m in matches if m.get("date") == tomorrow and not m.get("score")]

        lines   = [f"📊 Матчів: {len(matches)} | Зіграно: {len(played)}\n"]
        alerts  = []

        if today_m:
            lines.append(f"*📅 СЬОГОДНІ — {today}:*")
            for m in today_m:
                sc = m.get("score")
                if sc:
                    ft = sc.get("ft", ["?", "?"])
                    lines.append(f"✅ {m['team1']} *{ft[0]}–{ft[1]}* {m['team2']}")
                    try:
                        g1, g2 = int(ft[0]), int(ft[1])
                        t1f = m["team1"] in FAVORITES
                        t2f = m["team2"] in FAVORITES
                        if not t1f and t2f and g1 > g2:
                            alerts.append(("bandwagon", m["team2"],
                                f"⚡ UPSET! {m['team1']} переміг {m['team2']}!"))
                        elif t1f and not t2f and g2 > g1:
                            alerts.append(("bandwagon", m["team1"],
                                f"⚡ UPSET! {m['team2']} переміг {m['team1']}!"))
                        if g1+g2 >= 5:
                            alerts.append(("apology", "",
                                f"🔥 Голевий матч! {m['team1']} {ft[0]}-{ft[1]} {m['team2']}"))
                        if g1+g2 == 0:
                            alerts.append(("foulplay", "", "😴 0-0 — FOUL PLAY пост!"))
                    except:
                        pass
                else:
                    lines.append(f"⏰ {m['team1']} vs {m['team2']} [{m.get('time','?')}]")
        else:
            lines.append("_Сьогодні матчів немає_")

        if tomrw_m:
            lines.append(f"\n*📅 ЗАВТРА:*")
            for m in tomrw_m[:4]:
                lines.append(f"🔜 {m['team1']} vs {m['team2']} [{m.get('time','?')}]")

        if played and not today_m:
            recent = sorted(played, key=lambda x: x.get("date",""), reverse=True)[:3]
            lines.append(f"\n*📊 ОСТАННІ РЕЗУЛЬТАТИ:*")
            for m in recent:
                ft = m["score"].get("ft", ["?","?"])
                lines.append(f"• {m['date']} | {m['team1']} *{ft[0]}–{ft[1]}* {m['team2']}")

        return "\n".join(lines), alerts

    except Exception as e:
        return f"❌ API Error: {e}", []


def fetch_news():
    results  = []
    feeds_ok = 0
    for source, url in RSS_FEEDS.items():
        try:
            import urllib.request
            req  = urllib.request.Request(url, headers=HEADERS)
            resp = urllib.request.urlopen(req, timeout=8)
            feed = feedparser.parse(resp.read())
            feeds_ok += 1
            for entry in feed.entries[:8]:
                title   = entry.get("title", "")
                summary = entry.get("summary", "")
                product, score, players, teams = score_text(title, summary)
                # Спрацьовує якщо: score>=2 АБО знайдено конкретного гравця/команду
                has_entity = len(players) > 0 or len(teams) > 0
                if score >= 2 or (score >= 1 and has_entity):
                    results.append({
                        "source":  source,
                        "title":   title[:100],
                        "product": product,
                        "score":   score,
                        "players": players,
                        "teams":   teams,
                    })
        except:
            pass
    results.sort(key=lambda x: x["score"], reverse=True)
    return results, feeds_ok


def build_verdict(news_items, api_alerts):
    counts = {"apology": 0, "bandwagon": 0, "var": 0}
    for i in news_items:
        counts[i["product"]] += 1

    if api_alerts:
        top = api_alerts[0]
        if top[0] == "bandwagon":
            return "bandwagon", f"🔥 UPSET! Постити ЗАРАЗ — {top[2]}"
        elif top[0] == "apology":
            return "apology", "🔥 Голевий матч! Постити Apology хук!"
        elif top[0] == "foulplay":
            return "foulplay", "😴 0-0 нічия — FOUL PLAY хук"

    if counts["var"] >= 2:
        return "var",       "🔥 VAR скандал — постити Certificate ЗАРАЗ"
    elif counts["bandwagon"] >= 2:
        return "bandwagon", "🔥 Команди вилітають — Bandwagon хук!"
    elif counts["apology"] >= 3:
        return "apology",   "📈 Гравець в тренді — Apology хук"
    elif sum(counts.values()) > 0:
        best = max(counts, key=counts.get)
        return best,        "📊 Є активність — дивись хуки"
    else:
        return "foulplay",  "😴 Тихо. FOUL PLAY хук завжди актуальний"

# ══════════════════════════════════════════════
# КОМАНДИ БОТА
# ══════════════════════════════════════════════

MAIN_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("⚽ Перевірити зараз",  callback_data="check")],
    [InlineKeyboardButton("📅 Матчі сьогодні",    callback_data="matches")],
    [InlineKeyboardButton("✍️ Хуки для постів",   callback_data="hooks")],
    [InlineKeyboardButton("🔗 Gumroad посилання", callback_data="links")],
    [InlineKeyboardButton("💡 Що постити?",        callback_data="verdict")],
])

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ *SoccerPaperwork Bot*\n\n"
        "Твій помічник для монетизації ЧС 2026\\.\n"
        "Натисни кнопку після кожного матчу —\n"
        "отримаєш готовий текст для Threads\\.\n\n"
        "*/check* — перевірити все\n"
        "*/matches* — матчі і результати\n"
        "*/hooks* — хуки для постів\n"
        "*/links* — посилання Gumroad\n"
        "*/verdict* — що постити прямо зараз",
        parse_mode="MarkdownV2",
        reply_markup=MAIN_KB
    )


async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    await msg.reply_text("🔄 Перевіряю матчі і новини...")

    match_text, api_alerts = fetch_matches()
    news_items, feeds_ok   = fetch_news()
    product, verdict_text  = build_verdict(news_items, api_alerts)

    top_news = ""
    seen = set()
    for item in news_items[:3]:
        p = item["product"]
        if p not in seen:
            seen.add(p)
            emoji = "🔴" if p=="var" else ("🟡" if p=="bandwagon" else "🟢")
            top_news += f"{emoji} [{item['source']}] {item['title'][:55]}\n"

    text = (
        f"⚽ *MATCH DAY CHECK*\n"
        f"_{datetime.now().strftime('%d %b — %H:%M')}_\n\n"
        f"{match_text}\n\n"
    )
    if api_alerts:
        text += "*⚡ АЛЕРТИ:*\n"
        for a in api_alerts[:2]:
            text += f"• {a[2]}\n"
        text += "\n"
    if top_news:
        text += f"*📰 ТОП НОВИНИ ({feeds_ok} feeds):*\n{top_news}\n"
    text += f"*🎯 ВЕРДИКТ:*\n{verdict_text}"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Показати хук", callback_data=f"hook_{product}")],
        [InlineKeyboardButton("🔗 Gumroad",       callback_data="links")],
        [InlineKeyboardButton("🔄 Оновити",       callback_data="check")],
        [InlineKeyboardButton("🏠 Меню",          callback_data="menu")],
    ])
    await msg.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def cmd_matches(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    match_text, _ = fetch_matches()
    await msg.reply_text(
        f"📅 *МАТЧІ — WC2026*\n\n{match_text}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Оновити", callback_data="matches")],
            [InlineKeyboardButton("🏠 Меню",    callback_data="menu")],
        ])
    )


async def cmd_hooks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    await msg.reply_text(
        "✍️ *ХУКИ ДЛЯ THREADS*\n\nВибери продукт:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔴 VAR Certificate $2.99",  callback_data="hook_var")],
            [InlineKeyboardButton("🟡 Bandwagon Form $1.99",   callback_data="hook_bandwagon")],
            [InlineKeyboardButton("🟢 Apology Form $1.99",     callback_data="hook_apology")],
            [InlineKeyboardButton("🟠 FOUL PLAY Game $4.99",   callback_data="hook_foulplay")],
            [InlineKeyboardButton("🏠 Меню",                   callback_data="menu")],
        ])
    )


async def cmd_links(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    await msg.reply_text(
        f"🔗 *GUMROAD ПОСИЛАННЯ*\n\n"
        f"📋 Bandwagon $1\\.99\n{GUMROAD['bandwagon']}\n\n"
        f"📋 Apology $1\\.99\n{GUMROAD['apology']}\n\n"
        f"📋 VAR Cert $2\\.99\n{GUMROAD['var']}\n\n"
        f"🎮 FOUL PLAY $4\\.99\n{GUMROAD['foulplay']}\n\n"
        f"📦 Bundle $9\\.99\n{GUMROAD['bundle']}",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Меню", callback_data="menu")]
        ])
    )


async def cmd_verdict(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    await msg.reply_text("🔄 Аналізую...")
    news_items, _         = fetch_news()
    _, api_alerts         = fetch_matches()
    product, verdict_text = build_verdict(news_items, api_alerts)
    await msg.reply_text(
        f"💡 *ЩО ПОСТИТИ ЗАРАЗ?*\n\n{verdict_text}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✍️ Показати хук", callback_data=f"hook_{product}")],
            [InlineKeyboardButton("🔄 Оновити",       callback_data="verdict")],
            [InlineKeyboardButton("🏠 Меню",          callback_data="menu")],
        ])
    )


async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data

    if data == "check":
        await cmd_check(update, ctx)
    elif data == "matches":
        await cmd_matches(update, ctx)
    elif data == "hooks":
        await cmd_hooks(update, ctx)
    elif data == "links":
        await cmd_links(update, ctx)
    elif data == "verdict":
        await cmd_verdict(update, ctx)
    elif data == "menu":
        await query.message.reply_text(
            "⚽ *SoccerPaperwork Bot*\nВибери дію:",
            parse_mode="Markdown",
            reply_markup=MAIN_KB
        )
    elif data.startswith("hook_"):
        product   = data.replace("hook_", "")
        hook_text = HOOKS.get(product, HOOKS["foulplay"])
        gumroad   = GUMROAD.get(product, GUMROAD["bundle"])
        await query.message.reply_text(
            f"{hook_text}\n\n🔗 {gumroad}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✍️ Інший хук", callback_data="hooks")],
                [InlineKeyboardButton("🏠 Меню",       callback_data="menu")],
            ])
        )


async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Не знаю цю команду. Напиши /start",
        reply_markup=MAIN_KB
    )


# ══════════════════════════════════════════════
# ЗАПУСК
# ══════════════════════════════════════════════

def main():
    if not TOKEN:
        print("❌ BOT_TOKEN не встановлений!")
        print("   Render → Environment → BOT_TOKEN = твій токен")
        return

    # Запускаємо веб-сервер в окремому потоці
    # (Render вимагає відкритий порт, також тримає бот живим)
    t = threading.Thread(target=run_web_server, daemon=True)
    t.start()
    print(f"✅ Web server started on port {PORT}")

    # Запускаємо бота
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("check",   cmd_check))
    app.add_handler(CommandHandler("matches", cmd_matches))
    app.add_handler(CommandHandler("hooks",   cmd_hooks))
    app.add_handler(CommandHandler("links",   cmd_links))
    app.add_handler(CommandHandler("verdict", cmd_verdict))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    print("✅ SoccerPaperwork Bot запущено!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
