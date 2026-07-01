import random
import logging
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
 
BOT_TOKEN = "8255241467:AAGX5ncD95g06Bg7TF32VY8PKIh6BhsYJ3c"
ADMIN_ID  = 1590570666
UZ        = ZoneInfo("Asia/Tashkent")
WEBAPP_URL = "https://zicoworldliga.netlify.app"
BAN_HOURS = 24
 
SUPABASE_URL = "https://wfpspsiikwdxmatavwwm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndmcHNwc2lpa3dkeG1hdGF2d3dtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI4MjYwMTcsImV4cCI6MjA5ODQwMjAxN30.a48U3deN-0Kjg3FC4Edy-m3Z71ru-LyHuohkFwkEyfw"
 
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=representation"
}
 
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
 
def now_uz():
    return datetime.now(UZ)
 
def today():
    return now_uz().strftime("%Y-%m-%d")
 
def db_get(table, params=""):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}{params}", headers=HEADERS)
    return r.json() if r.ok else []
 
def db_post(table, data):
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=data)
    return r.json() if r.ok else None
 
def db_patch(table, data, params):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}{params}", headers=HEADERS, json=data)
    return r.ok
 
def db_delete(table, params):
    r = requests.delete(f"{SUPABASE_URL}/rest/v1/{table}{params}", headers=HEADERS)
    return r.ok
 
def save_user(user):
    db_post("users", {
        "id": user.id,
        "username": user.username or user.first_name,
        "first_name": user.first_name or ""
    })
 
def get_user(uid):
    res = db_get("users", f"?id=eq.{uid}")
    return res[0] if res else None
 
def get_my_match(uid):
    res = db_get("matches", f"?or=(player1_id.eq.{uid},player2_id.eq.{uid})&status=neq.done&order=id.desc&limit=1")
    if not res:
        return None
    m = res[0]
    p1 = get_user(m["player1_id"])
    p2 = get_user(m["player2_id"])
    m["p1_name"] = p1["username"] if p1 else "?"
    m["p2_name"] = p2["username"] if p2 else "?"
    return m
 
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    text = (
        f"👋 <b>Salom, {user.first_name}!</b>\n\n"
        f"🏆 <b>ZICO WORLD LIGA</b> ga xush kelibsiz!\n\n"
        f"⬇️ Ilovani oching va chempionatga qatnashing!"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🏆 Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])
    if update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
 
async def cmd_hisob(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    m = get_my_match(uid)
    if not m:
        await update.message.reply_text(
            "❗ Sizda hozir faol o'yin yo'q.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏆 Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))
            ]])
        )
        return
    rival_u = m["p2_name"] if uid == m["player1_id"] else m["p1_name"]
    await update.message.reply_text(
        f"⚽ <b>Hisob kiritish</b>\n\nRaqibingiz: <b>@{rival_u}</b>\n\n"
        f"Format: <code>siz-raqib</code>\nMisol: <code>3-1</code>",
        parse_mode="HTML"
    )
    ctx.user_data["score_match"] = True
 
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        return
    total   = len(db_get("users", "?select=id"))
    today_r = len(db_get("registrations", f"?season_date=eq.{today()}&select=id"))
    total_m = len(db_get("matches", "?select=id"))
    await update.message.reply_text(
        f"👑 <b>ADMIN PANEL</b>\n\n"
        f"👥 Jami: <b>{total}</b>\n"
        f"📋 Bugun: <b>{today_r}</b>\n"
        f"⚔️ O'yinlar: <b>{total_m}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⚔️ Qur'a tashlash", callback_data="admin_draw")
        ]])
    )
 
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    if ctx.user_data.get("score_match"):
        ctx.user_data.pop("score_match", None)
        await process_score(update, ctx, uid, text)
        return
    await update.message.reply_text(
        "Ilovani ochish uchun /start yozing.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏆 Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))
        ]])
    )
 
async def process_score(update, ctx, uid, text):
    parts = text.split("-")
    if len(parts) != 2 or not parts[0].strip().isdigit() or not parts[1].strip().isdigit():
        await update.message.reply_text("❗ Format: <code>3-1</code>", parse_mode="HTML")
        ctx.user_data["score_match"] = True
        return
    m = get_my_match(uid)
    if not m:
        await update.message.reply_text("❗ Sizda faol o'yin yo'q.")
        return
    my_g  = int(parts[0].strip())
    opp_g = int(parts[1].strip())
    rival_id = m["player2_id"] if uid == m["player1_id"] else m["player1_id"]
    rival_u  = m["p2_name"]    if uid == m["player1_id"] else m["p1_name"]
    my_u     = update.effective_user.username or update.effective_user.first_name
    winner_id = uid if my_g > opp_g else (rival_id if opp_g > my_g else None)
    db_patch("matches", {
        "score": text, "submitted_by": uid,
        "winner_id": winner_id, "submitted_at": now_uz().isoformat(), "status": "awaiting"
    }, f"?id=eq.{m['id']}")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ha, to'g'ri", callback_data=f"confirm:{m['id']}"),
        InlineKeyboardButton("❌ Xato", callback_data=f"deny:{m['id']}")
    ]])
    try:
        await ctx.bot.send_message(rival_id,
            f"⚽ <b>Hisob tasdiqlash!</b>\n@{my_u} yubordi: <b>{text}</b>\nTo'g'rimi?",
            parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.error(e)
    await update.message.reply_text(f"✅ Hisob yuborildi: <b>{text}</b>", parse_mode="HTML")
 
async def callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()
    if q.data == "home":
        await cmd_start(update, ctx)
    elif q.data == "admin_draw":
        await do_draw(ctx.bot)
        await q.message.edit_text("✅ Qur'a tashlandi!")
    elif q.data.startswith("confirm:"):
        mid = int(q.data.split(":")[1])
        await do_confirm(q, ctx, uid, mid, "yes")
    elif q.data.startswith("deny:"):
        mid = int(q.data.split(":")[1])
        await do_confirm(q, ctx, uid, mid, "no")
 
async def do_confirm(q, ctx, uid, mid, action):
    res = db_get("matches", f"?id=eq.{mid}")
    if not res:
        await q.message.edit_text("✅ Allaqachon tugallangan.")
        return
    m = res[0]
    if m["status"] == "done":
        await q.message.edit_text("✅ Allaqachon tugallangan.")
        return
    if uid == m["submitted_by"]:
        await q.answer("❌ O'z hisobingizni tasdiqlay olmaysiz!", show_alert=True)
        return
    p1 = get_user(m["player1_id"])
    p2 = get_user(m["player2_id"])
    m["p1_name"] = p1["username"] if p1 else "?"
    m["p2_name"] = p2["username"] if p2 else "?"
    if action == "yes":
        db_patch("matches", {"status": "done", "confirmed": 1}, f"?id=eq.{mid}")
        if m["winner_id"] is None:
            for pid in [m["player1_id"], m["player2_id"]]:
                u = get_user(pid)
                if u:
                    db_patch("users", {"points": u["points"]+5, "draws": u["draws"]+1}, f"?id=eq.{pid}")
            result = f"🤝 Durang! {m['p1_name']} vs {m['p2_name']} — {m['score']}\n+5 ball"
        else:
            loser_id = m["player2_id"] if m["winner_id"]==m["player1_id"] else m["player1_id"]
            wu = get_user(m["winner_id"])
            lu = get_user(loser_id)
            if wu: db_patch("users", {"points": wu["points"]+15, "wins": wu["wins"]+1}, f"?id=eq.{m['winner_id']}")
            if lu: db_patch("users", {"points": max(0,lu["points"]-10), "losses": lu["losses"]+1}, f"?id=eq.{loser_id}")
            wn = m["p1_name"] if m["winner_id"]==m["player1_id"] else m["p2_name"]
            result = f"🏆 {m['p1_name']} {m['score']} {m['p2_name']}\nG'olib: @{wn} (+15)\nMag'lub: -10 ball"
        for pid in [m["player1_id"], m["player2_id"]]:
            try: await ctx.bot.send_message(pid, result)
            except: pass
        await q.message.edit_text(result)
    else:
        db_patch("matches", {"status":"pending","score":None,"submitted_by":None,"winner_id":None}, f"?id=eq.{mid}")
        rival_id = m["player2_id"] if uid==m["player1_id"] else m["player1_id"]
        try: await ctx.bot.send_message(rival_id, "❌ Hisob rad etildi. Qayta kiriting: /hisob")
        except: pass
        await q.message.edit_text("❌ Hisob rad etildi.")
 
async def do_draw(bot):
    regs = db_get("registrations", f"?season_date=eq.{today()}&select=user_id")
    if len(regs) < 2:
        return
    parts = [get_user(r["user_id"]) for r in regs]
    parts = [p for p in parts if p]
    random.shuffle(parts)
    dl = (now_uz() + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)
    if len(parts) % 2 == 1:
        lone = parts.pop()
        db_patch("users", {"points": lone["points"]+15, "wins": lone["wins"]+1}, f"?id=eq.{lone['id']}")
        try: await bot.send_message(lone["id"], "🏆 Raqib topilmadi — avtomatik G'ALABA! +15 ball")
        except: pass
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏆 Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))]])
    for i in range(0, len(parts)-1, 2):
        p1, p2 = parts[i], parts[i+1]
        db_post("matches", {
            "player1_id": p1["id"], "player2_id": p2["id"],
            "season_date": today(), "deadline": dl.isoformat()
        })
        msg = (f"⚔️ <b>RAQIBINGIZ ANIQLANDI!</b>\n\n"
               f"@{p1['username']} VS @{p2['username']}\n\n"
               f"Hisob kiritish: /hisob")
        try: await bot.send_message(p1["id"], msg, parse_mode="HTML", reply_markup=kb)
        except: pass
        try: await bot.send_message(p2["id"], msg, parse_mode="HTML", reply_markup=kb)
        except: pass
 
async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "Botni ishga tushirish"),
        BotCommand("hisob", "O'yin hisobini kiritish"),
        BotCommand("admin", "Admin panel"),
    ])
 
def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("hisob", cmd_hisob))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("✅ Zico World Liga bot ishga tushdi!")
    app.run_polling(allowed_updates=["message", "callback_query"])
 
if __name__ == "__main__":
    main()