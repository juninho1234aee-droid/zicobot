import random
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from supabase import create_client, Client
 
# ═══════════════════════════
# SOZLAMALAR
# ═══════════════════════════
BOT_TOKEN = "8255241467:AAGX5ncD95g06Bg7TF32VY8PKIh6BhsYJ3c"
ADMIN_ID  = 1590570666
UZ        = ZoneInfo("Asia/Tashkent")
 
# TEST UCHUN: ro'yxat hozir ochiq bo'lishi uchun joriy vaqtga moslab qo'yilgan.
# Haqiqiy ishga tushirishda buni o'zingiz xohlagan vaqtga o'zgartiring (soat, daqiqa).
REG_START = (0, 0)     # ro'yxat ochiladigan vaqt (soat, daqiqa)
REG_END   = (23, 59)   # ro'yxat yopiladigan vaqt (soat, daqiqa)
 
BAN_HOURS = 24
WEBAPP_URL = "https://zicoworldliga.netlify.app"
 
SUPABASE_URL = "https://wfpspsiikwdxmatavwwm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndmcHNwc2lpa3dkeG1hdGF2d3dtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI4MjYwMTcsImV4cCI6MjA5ODQwMjAxN30.a48U3deN-0Kjg3FC4Edy-m3Z71ru-LyHuohkFwkEyfw"
 
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
 
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
 
# ═══════════════════════════
# YORDAMCHILAR
# ═══════════════════════════
def now_uz():
    return datetime.now(UZ)
 
def today():
    return now_uz().strftime("%Y-%m-%d")
 
def is_reg_open():
    n = now_uz()
    now_m = n.hour * 60 + n.minute
    return REG_START[0]*60+REG_START[1] <= now_m < REG_END[0]*60+REG_END[1]
 
def countdown_to(h, m):
    n = now_uz()
    tgt = n.replace(hour=h, minute=m, second=0, microsecond=0)
    if n >= tgt:
        tgt += timedelta(days=1)
    diff = int((tgt - n).total_seconds())
    return f"{diff//3600:02d}:{(diff%3600)//60:02d}:{diff%60:02d}"
 
def save_user(user):
    sb.table("users").upsert({
        "id": user.id,
        "username": user.username or user.first_name,
        "first_name": user.first_name
    }).execute()
 
def get_user(uid):
    res = sb.table("users").select("*").eq("id", uid).execute()
    return res.data[0] if res.data else None
 
def is_banned(uid):
    u = get_user(uid)
    if u and u.get("ban_until"):
        ban_dt = datetime.fromisoformat(u["ban_until"].replace("Z", "+00:00"))
        if now_uz() < ban_dt:
            return True, ban_dt
        sb.table("users").update({"ban_until": None}).eq("id", uid).execute()
    return False, None
 
def get_my_match(uid):
    res = sb.table("matches").select("*").or_(
        f"player1_id.eq.{uid},player2_id.eq.{uid}"
    ).neq("status", "done").order("id", desc=True).limit(1).execute()
    if not res.data:
        return None
    m = res.data[0]
    p1 = get_user(m["player1_id"])
    p2 = get_user(m["player2_id"])
    m["p1_name"] = p1["username"] if p1 else "?"
    m["p2_name"] = p2["username"] if p2 else "?"
    return m
 
def get_rating():
    res = sb.table("users").select("*").order("points", desc=True).execute()
    return res.data
 
# ═══════════════════════════
# /start — FAQAT 1 TUGMA
# ═══════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
 
    if is_reg_open():
        cd = countdown_to(REG_END[0], REG_END[1])
        status = f"🟢 Ro'yxat OCHIQ — {cd} qoldi"
    else:
        cd = countdown_to(REG_START[0], REG_START[1])
        status = f"🔴 Ro'yxat yopiq — {cd} da ochiladi"
 
    text = (
        f"👋 <b>Salom, {user.first_name}!</b>\n\n"
        f"🏆 <b>ZICO WORLD LIGA</b> ga xush kelibsiz!\n\n"
        f"📌 {status}\n\n"
        f"⬇️ Ilovani oching va chempionatga qatnashing!"
    )
 
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
 
    if update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
 
# ═══════════════════════════
# CALLBACK
# ═══════════════════════════
async def callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()
 
    if q.data == "home":
        await cmd_start(update, ctx)
    elif q.data == "admin":
        await show_admin(q, uid)
    elif q.data == "admin_draw":
        await admin_draw_cb(q)
    elif q.data.startswith("confirm:"):
        mid = int(q.data.split(":")[1])
        await do_confirm(q, ctx, uid, mid, "yes")
    elif q.data.startswith("deny:"):
        mid = int(q.data.split(":")[1])
        await do_confirm(q, ctx, uid, mid, "no")
    elif q.data == "enter_score":
        await q.message.reply_text(
            "⚽ <b>Hisob kiriting:</b>\n\n"
            "Format: <code>siz-raqib</code>\n"
            "Misol: <code>3-1</code>",
            parse_mode="HTML"
        )
        ctx.user_data["score_match"] = True
 
# ═══════════════════════════
# HISOB KIRITISH
# ═══════════════════════════
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
 
    if ctx.user_data.get("score_match"):
        ctx.user_data.pop("score_match", None)
        await process_score(update, ctx, uid, text)
        return
 
    if update.message.web_app_data:
        await update.message.reply_text("✅ Ma'lumot qabul qilindi!")
        return
 
    await update.message.reply_text(
        "Ilovani ochish uchun /start yozing.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏆 Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))]
        ])
    )
 
async def process_score(update, ctx, uid, text):
    parts = text.split("-")
    if len(parts) != 2 or not parts[0].strip().isdigit() or not parts[1].strip().isdigit():
        await update.message.reply_text(
            "❗ Noto'g'ri format!\nMisol: <code>3-1</code>",
            parse_mode="HTML"
        )
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
 
    sb.table("matches").update({
        "score": text,
        "submitted_by": uid,
        "winner_id": winner_id,
        "submitted_at": now_uz().isoformat(),
        "status": "awaiting"
    }).eq("id", m["id"]).execute()
 
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ha, to'g'ri", callback_data=f"confirm:{m['id']}"),
        InlineKeyboardButton("❌ Xato",        callback_data=f"deny:{m['id']}")
    ]])
 
    try:
        await ctx.bot.send_message(
            rival_id,
            f"⚽ <b>Hisob tasdiqlash kerak!</b>\n\n"
            f"@{my_u} hisob yubordi: <b>{text}</b>\n\n"
            f"To'g'rimi?\n"
            f"⚠️ <b>30 daqiqa ichida tasdiqlanmasa — {BAN_HOURS} soat ban!</b>",
            parse_mode="HTML", reply_markup=kb
        )
    except Exception as e:
        logger.error(e)
 
    await update.message.reply_text(
        f"✅ Hisob yuborildi: <b>{text}</b>\n@{rival_u} tasdiqlashini kuting.",
        parse_mode="HTML"
    )
 
    ctx.job_queue.run_once(
        ban_check_job, when=30*60,
        data={"mid": m["id"], "rival_id": rival_id, "rival_u": rival_u, "my_id": uid}
    )
 
# ═══════════════════════════
# TASDIQLASH
# ═══════════════════════════
async def do_confirm(q, ctx, uid, mid, action):
    res = sb.table("matches").select("*").eq("id", mid).execute()
    if not res.data:
        await q.message.edit_text("✅ Bu o'yin allaqachon tugallangan.")
        return
    m = res.data[0]
    p1 = get_user(m["player1_id"])
    p2 = get_user(m["player2_id"])
    m["p1_name"] = p1["username"] if p1 else "?"
    m["p2_name"] = p2["username"] if p2 else "?"
 
    if m["status"] == "done":
        await q.message.edit_text("✅ Bu o'yin allaqachon tugallangan.")
        return
 
    if uid == m["submitted_by"]:
        await q.answer("❌ O'z hisobingizni tasdiqlay olmaysiz!", show_alert=True)
        return
 
    rival_id = m["player2_id"] if uid == m["player1_id"] else m["player1_id"]
 
    if action == "yes":
        sb.table("matches").update({"status": "done", "confirmed": 1}).eq("id", mid).execute()
        is_draw = m["winner_id"] is None
        if is_draw:
            for pid in [m["player1_id"], m["player2_id"]]:
                u = get_user(pid)
                sb.table("users").update({
                    "points": u["points"] + 5, "draws": u["draws"] + 1
                }).eq("id", pid).execute()
            result = (f"🤝 <b>Durang!</b>\n@{m['p1_name']} vs @{m['p2_name']} — {m['score']}\n"
                     f"Ikkalangiz +5 ball oldingiz!")
        else:
            loser_id = m["player2_id"] if m["winner_id"] == m["player1_id"] else m["player1_id"]
            wu = get_user(m["winner_id"])
            lu = get_user(loser_id)
            sb.table("users").update({
                "points": wu["points"] + 15, "wins": wu["wins"] + 1
            }).eq("id", m["winner_id"]).execute()
            sb.table("users").update({
                "points": max(0, lu["points"] - 10), "losses": lu["losses"] + 1
            }).eq("id", loser_id).execute()
            w_u = m["p1_name"] if m["winner_id"] == m["player1_id"] else m["p2_name"]
            l_u = m["p2_name"] if m["winner_id"] == m["player1_id"] else m["p1_name"]
            result = (f"🏆 <b>Natija tasdiqlandi!</b>\n"
                     f"@{m['p1_name']} {m['score']} @{m['p2_name']}\n\n"
                     f"✅ G'olib: @{w_u} (+15 ball)\n❌ Mag'lub: @{l_u} (-10 ball)")
 
        for pid in [m["player1_id"], m["player2_id"]]:
            try:
                await ctx.bot.send_message(pid, result, parse_mode="HTML")
            except:
                pass
        await q.message.edit_text(result, parse_mode="HTML")
 
    else:
        sb.table("matches").update({
            "status": "pending", "score": None, "submitted_by": None,
            "winner_id": None, "submitted_at": None
        }).eq("id", mid).execute()
        try:
            await ctx.bot.send_message(rival_id,
                "❌ Raqibingiz hisobni rad etdi.\nQayta hisob kiriting: /hisob")
        except:
            pass
        await q.message.edit_text("❌ Hisob rad etildi. Raqib qayta kiritishi kerak.")
 
# ═══════════════════════════
# BAN CHECK
# ═══════════════════════════
async def ban_check_job(ctx: ContextTypes.DEFAULT_TYPE):
    d = ctx.job.data
    res = sb.table("matches").select("status").eq("id", d["mid"]).execute()
    if not res.data or res.data[0]["status"] == "done":
        return
    ban_until = (now_uz() + timedelta(hours=BAN_HOURS)).isoformat()
    sb.table("users").update({"ban_until": ban_until}).eq("id", d["rival_id"]).execute()
    try:
        await ctx.bot.send_message(d["rival_id"],
            f"🚫 <b>{BAN_HOURS} soatlik ban!</b>\n\n"
            f"30 daqiqa ichida hisobni tasdiqlamadingiz.",
            parse_mode="HTML")
        await ctx.bot.send_message(d["my_id"],
            f"ℹ️ @{d['rival_u']} {BAN_HOURS} soat ban oldi.")
    except:
        pass
 
# ═══════════════════════════
# ADMIN
# ═══════════════════════════
async def show_admin(q, uid):
    if uid != ADMIN_ID:
        await q.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    total   = len(sb.table("users").select("id").execute().data)
    today_r = len(sb.table("registrations").select("id").eq("season_date", today()).execute().data)
    total_m = len(sb.table("matches").select("id").execute().data)
    done_m  = len(sb.table("matches").select("id").eq("status", "done").execute().data)
 
    await q.message.edit_text(
        f"👑 <b>ADMIN PANEL</b>\n\n"
        f"👥 Jami a'zolar: <b>{total}</b>\n"
        f"📋 Bugun ro'yxatda: <b>{today_r}</b>\n"
        f"⚔️ Jami o'yinlar: <b>{total_m}</b>\n"
        f"✅ Tugallangan: <b>{done_m}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚔️ Qur'a tashlash", callback_data="admin_draw")],
            [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="home")]
        ])
    )
 
async def admin_draw_cb(q):
    if q.from_user.id != ADMIN_ID:
        return
    await do_draw(q.get_bot())
    await q.message.edit_text("✅ Qur'a tashlandi!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="home")]
        ]))
 
async def do_draw(bot):
    regs = sb.table("registrations").select("user_id").eq("season_date", today()).execute().data
 
    if len(regs) < 2:
        if len(regs) == 1:
            await bot.send_message(regs[0]["user_id"],
                "⚠️ Bugun chempionat bo'lmadi — ishtirokchi kam.")
        return
 
    parts = []
    for r in regs:
        u = get_user(r["user_id"])
        parts.append(u)
    random.shuffle(parts)
    dl = now_uz().replace(hour=17, minute=0, second=0, microsecond=0) + timedelta(days=1)
 
    if len(parts) % 2 == 1:
        lone = parts.pop()
        sb.table("users").update({
            "points": lone["points"] + 15, "wins": lone["wins"] + 1
        }).eq("id", lone["id"]).execute()
        await bot.send_message(lone["id"],
            "🏆 Raqib topilmadi — avtomatik <b>G'ALABA</b>!\n+15 ball qo'shildi.",
            parse_mode="HTML")
 
    for i in range(0, len(parts)-1, 2):
        p1, p2 = parts[i], parts[i+1]
        sb.table("matches").insert({
            "player1_id": p1["id"], "player2_id": p2["id"],
            "season_date": today(), "deadline": dl.isoformat()
        }).execute()
        msg = (
            f"⚔️ <b>RAQIBINGIZ ANIQLANDI!</b>\n\n"
            f"👤 @{p1['username']}\n         <b>VS</b>\n👤 @{p2['username']}\n\n"
            f"📅 Deadline: {dl.strftime('%d.%m.%Y %H:%M')} gacha\n"
            f"⚠️ O'ynamasangiz — <b>{BAN_HOURS} soat ban!</b>\n\n"
            f"Hisobni kiritish: /hisob"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏆 Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))]
        ])
        await bot.send_message(p1["id"], msg, parse_mode="HTML", reply_markup=kb)
        await bot.send_message(p2["id"], msg, parse_mode="HTML", reply_markup=kb)
 
# ═══════════════════════════
# /hisob
# ═══════════════════════════
async def cmd_hisob(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    m = get_my_match(uid)
    if not m:
        await update.message.reply_text(
            "❗ Sizda hozir faol o'yin yo'q.\n\n"
            "Qur'a tashlanganidan keyin bu buyruqdan foydalaning.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏆 Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))]
            ])
        )
        return
    rival_u = m["p2_name"] if uid == m["player1_id"] else m["p1_name"]
    await update.message.reply_text(
        f"⚽ <b>Hisob kiritish</b>\n\nRaqibingiz: <b>@{rival_u}</b>\n\n"
        f"Hisobni yozing <b>(siz – raqib)</b>:\nMisol: <code>3-1</code>",
        parse_mode="HTML"
    )
    ctx.user_data["score_match"] = True
 
# ═══════════════════════════
# ADMIN BUYRUQLARI
# ═══════════════════════════
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        return
    total   = len(sb.table("users").select("id").execute().data)
    today_r = len(sb.table("registrations").select("id").eq("season_date", today()).execute().data)
    total_m = len(sb.table("matches").select("id").execute().data)
    await update.message.reply_text(
        f"👑 <b>ADMIN PANEL</b>\n\n"
        f"👥 Jami: <b>{total}</b>\n"
        f"📋 Bugun: <b>{today_r}</b>\n"
        f"⚔️ O'yinlar: <b>{total_m}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚔️ Qur'a tashlash", callback_data="admin_draw")]
        ])
    )
 
# ═══════════════════════════
# SCHEDULED JOBS
# ═══════════════════════════
async def job_notify(ctx: ContextTypes.DEFAULT_TYPE):
    users = sb.table("users").select("id").execute().data
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    for u in users:
        try:
            await ctx.bot.send_message(u["id"],
                "🔔 <b>CHEMPIONAT BOSHLANDI!</b>\n\n"
                "⏰ Ro'yxat: 17:00 – 18:00\n"
                "⚔️ Qur'a: 18:00 da\n\n"
                "Ilovani oching va qatnashing! 👇",
                parse_mode="HTML", reply_markup=kb)
        except:
            pass
 
async def job_draw(ctx: ContextTypes.DEFAULT_TYPE):
    await do_draw(ctx.bot)
 
# ═══════════════════════════
# MAIN
# ═══════════════════════════
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
 
    app.job_queue.run_daily(job_notify,
        time=datetime.now(UZ).replace(hour=17,minute=0,second=0).timetz())
    app.job_queue.run_daily(job_draw,
        time=datetime.now(UZ).replace(hour=18,minute=0,second=0).timetz())
 
    logger.info("✅ Zico World Liga bot ishga tushdi!")
    app.run_polling(allowed_updates=["message","callback_query"])
 
if __name__ == "__main__":
    main()
