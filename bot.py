import random
import logging
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
 
BOT_TOKEN  = "8255241467:AAGX5ncD95g06Bg7TF32VY8PKIh6BhsYJ3c"
ADMIN_ID   = 1590570666
UZ         = ZoneInfo("Asia/Tashkent")
WEBAPP_URL = "https://zicoworldliga.netlify.app"
BAN_HOURS  = 24
CONFIRM_MIN = 30
 
# Ball tizimi
WIN_PTS   = 15
DRAW_PTS  = 5
LOSS_PTS  = 20   # ayiriladi
TOP3_WIN  = 30   # top3 ni yutsa
TOP3_LOSS = 25   # top3 yutqizsa ayiriladi
 
# Mavsum
SEASON_NUM   = 1
SEASON_START = datetime(2026, 7, 7, 7, 0, 0, tzinfo=ZoneInfo("Asia/Tashkent"))
SEASON_END   = datetime(2026, 8, 7, 7, 0, 0, tzinfo=ZoneInfo("Asia/Tashkent"))
 
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
 
# ═══════════════════════════
# DB HELPERS
# ═══════════════════════════
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
 
def now_uz():
    return datetime.now(UZ)
 
def today():
    return now_uz().strftime("%Y-%m-%d")
 
# ═══════════════════════════
# USER HELPERS
# ═══════════════════════════
def save_user(user, photo_url=None):
    data = {
        "id": user.id,
        "username": user.username or user.first_name,
        "first_name": user.first_name or ""
    }
    if photo_url:
        data["photo_url"] = photo_url
    db_post("users", data)
 
def get_user(uid):
    res = db_get("users", f"?id=eq.{uid}")
    return res[0] if res else None
 
def get_top3_ids():
    res = db_get("users", "?order=points.desc&select=id&limit=3")
    return [r["id"] for r in res] if res else []
 
def get_rank(uid):
    all_u = db_get("users", "?order=points.desc&select=id")
    for i, u in enumerate(all_u):
        if u["id"] == uid:
            return i + 1
    return None
 
def is_banned(uid):
    u = get_user(uid)
    if u and u.get("ban_until"):
        try:
            ban_dt = datetime.fromisoformat(u["ban_until"].replace("Z", "+00:00"))
            if now_uz() < ban_dt:
                return True, ban_dt
            db_patch("users", {"ban_until": None}, f"?id=eq.{uid}")
        except:
            pass
    return False, None
 
def get_my_match(uid):
    res = db_get("matches", f"?or=(player1_id.eq.{uid},player2_id.eq.{uid})&status=neq.done&order=id.desc&limit=1")
    if not res:
        return None
    m = res[0]
    p1 = get_user(m["player1_id"])
    p2 = get_user(m["player2_id"])
    m["p1_name"] = p1["username"] if p1 else "?"
    m["p2_name"] = p2["username"] if p2 else "?"
    m["p1_photo"] = p1.get("photo_url") if p1 else None
    m["p2_photo"] = p2.get("photo_url") if p2 else None
    return m
 
# ═══════════════════════════
# NAVBAT (QUEUE)
# ═══════════════════════════
def get_queue():
    return db_get("queue", "?select=*&order=created_at.asc")
 
def in_queue(uid):
    res = db_get("queue", f"?user_id=eq.{uid}")
    return len(res) > 0
 
def add_to_queue(uid):
    db_post("queue", {"user_id": uid, "created_at": now_uz().isoformat()})
 
def remove_from_queue(uid):
    db_delete("queue", f"?user_id=eq.{uid}")
 
# ═══════════════════════════
# MAVSUM
# ═══════════════════════════
def get_season_status():
    n = now_uz()
    if n < SEASON_START:
        diff = int((SEASON_START - n).total_seconds())
        h = diff // 3600
        m = (diff % 3600) // 60
        return "waiting", f"{h}:{m:02d}"
    elif n < SEASON_END:
        diff = int((SEASON_END - n).total_seconds())
        d = diff // 86400
        return "active", f"{d} kun"
    else:
        return "ended", None
 
# ═══════════════════════════
# /start
# ═══════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
 
    # Profil rasmini olish
    try:
        photos = await ctx.bot.get_user_profile_photos(user.id, limit=1)
        photo_url = None
        if photos.total_count > 0:
            file = await ctx.bot.get_file(photos.photos[0][-1].file_id)
            photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
        save_user(user, photo_url)
    except:
        save_user(user)
 
    status, info = get_season_status()
    banned, ban_dt = is_banned(user.id)
 
    if banned:
        text = (f"👋 <b>Salom, {user.first_name}!</b>\n\n"
                f"🚫 Siz {ban_dt.strftime('%d.%m %H:%M')} gacha bansiz.")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🏆 Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))
        ]])
        if update.message:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
        return
 
    if status == "waiting":
        season_text = f"⏳ <b>1-mavsum</b> {info} da boshlanadi\n📅 Boshlanish: 7-iyul 07:00"
    elif status == "active":
        season_text = f"🟢 <b>1-mavsum</b> faol — {info} qoldi"
    else:
        season_text = f"🏁 <b>1-mavsum</b> tugadi"
 
    m = get_my_match(user.id)
    match_text = ""
    if m:
        rival = m["p2_name"] if user.id == m["player1_id"] else m["p1_name"]
        match_text = f"\n\n⚔️ <b>Joriy o'yin:</b> @{rival} bilan"
 
    text = (f"👋 <b>Salom, {user.first_name}!</b>\n\n"
            f"🏆 <b>ZICO WORLD LIGA</b>\n"
            f"{season_text}{match_text}\n\n"
            f"⬇️ Ilovani oching!")
 
    buttons = [[InlineKeyboardButton("🏆 Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))]]
 
    if status == "active" and not m:
        buttons.insert(0, [InlineKeyboardButton("⚡ Raqib qidirish", callback_data="find_match")])
 
    if m:
        buttons.insert(0, [InlineKeyboardButton("⚽ Hisob kiritish", callback_data="enter_score")])
 
    if user.id == ADMIN_ID:
        buttons.append([InlineKeyboardButton("👑 Admin panel", callback_data="admin")])
 
    kb = InlineKeyboardMarkup(buttons)
    if update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
 
# ═══════════════════════════
# RAQIB QIDIRISH
# ═══════════════════════════
async def find_match_cb(q, ctx):
    uid = q.from_user.id
    user = q.from_user
 
    banned, ban_dt = is_banned(uid)
    if banned:
        await q.answer(f"🚫 {ban_dt.strftime('%d.%m %H:%M')} gacha bansiz!", show_alert=True)
        return
 
    m = get_my_match(uid)
    if m:
        await q.answer("⚠️ Sizda allaqachon faol o'yin bor!", show_alert=True)
        return
 
    if in_queue(uid):
        await q.answer("⏳ Allaqachon navbatdasiz!", show_alert=True)
        return
 
    queue = get_queue()
    waiting = [x for x in queue if x["user_id"] != uid]
 
    if waiting:
        rival_id = waiting[0]["user_id"]
        remove_from_queue(rival_id)
 
        rival = get_user(rival_id)
        my_user = get_user(uid)
 
        db_post("matches", {
            "player1_id": uid,
            "player2_id": rival_id,
            "season_date": today(),
            "season_num": SEASON_NUM,
            "deadline": (now_uz() + timedelta(hours=24)).isoformat()
        })
 
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("⚽ Hisob kiritish", callback_data="enter_score"),
            InlineKeyboardButton("🏆 Ilova", web_app=WebAppInfo(url=WEBAPP_URL))
        ]])
 
        msg = (f"⚔️ <b>RAQIB TOPILDI!</b>\n\n"
               f"👤 @{my_user['username'] if my_user else user.first_name}\n"
               f"          🆚\n"
               f"👤 @{rival['username'] if rival else '?'}\n\n"
               f"⏱ 30 daqiqa ichida hisob kiriting!\n"
               f"⚠️ Kiritmasa — {BAN_HOURS} soat ban!")
 
        try:
            await ctx.bot.send_message(rival_id, msg, parse_mode="HTML", reply_markup=kb)
        except Exception as e:
            logger.error(e)
 
        await q.message.edit_text(msg, parse_mode="HTML", reply_markup=kb)
 
    else:
        add_to_queue(uid)
        await q.message.edit_text(
            f"⏳ <b>Raqib qidirilmoqda...</b>\n\n"
            f"Navbatda kutayapsiz. Raqib topilsa darhol xabar beramiz!\n\n"
            f"Bekor qilish uchun /start bosing.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Navbatdan chiqish", callback_data="leave_queue")
            ]])
        )
 
# ═══════════════════════════
# HISOB KIRITISH
# ═══════════════════════════
async def enter_score_cb(q, ctx):
    uid = q.from_user.id
    m = get_my_match(uid)
    if not m:
        await q.answer("❗ Faol o'yin yo'q!", show_alert=True)
        return
    rival = m["p2_name"] if uid == m["player1_id"] else m["p1_name"]
    await q.message.reply_text(
        f"⚽ <b>Hisob kiritish</b>\n\n"
        f"Raqib: <b>@{rival}</b>\n\n"
        f"Format: <code>siz-raqib</code>\n"
        f"Misol: <code>3-1</code>",
        parse_mode="HTML"
    )
    ctx.user_data["score_match"] = True
 
async def process_score(update, ctx, uid, text):
    parts = text.split("-")
    if len(parts) != 2 or not parts[0].strip().isdigit() or not parts[1].strip().isdigit():
        await update.message.reply_text("❗ Format: <code>3-1</code>", parse_mode="HTML")
        ctx.user_data["score_match"] = True
        return
 
    m = get_my_match(uid)
    if not m:
        await update.message.reply_text("❗ Faol o'yin yo'q.")
        return
 
    my_g  = int(parts[0].strip())
    opp_g = int(parts[1].strip())
    rival_id = m["player2_id"] if uid == m["player1_id"] else m["player1_id"]
    rival_u  = m["p2_name"]    if uid == m["player1_id"] else m["p1_name"]
    my_u     = update.effective_user.username or update.effective_user.first_name
    winner_id = uid if my_g > opp_g else (rival_id if opp_g > my_g else None)
 
    db_patch("matches", {
        "score": text, "submitted_by": uid,
        "winner_id": winner_id,
        "submitted_at": now_uz().isoformat(),
        "status": "awaiting"
    }, f"?id=eq.{m['id']}")
 
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ha, to'g'ri", callback_data=f"confirm:{m['id']}"),
        InlineKeyboardButton("❌ Xato", callback_data=f"deny:{m['id']}")
    ]])
 
    try:
        await ctx.bot.send_message(
            rival_id,
            f"⚽ <b>Hisob tasdiqlash!</b>\n\n"
            f"@{my_u} yubordi: <b>{text}</b>\n\n"
            f"To'g'rimi?\n"
            f"⚠️ <b>{CONFIRM_MIN} daqiqa ichida tasdiqlanmasa — {BAN_HOURS} soat ban!</b>",
            parse_mode="HTML", reply_markup=kb
        )
    except Exception as e:
        logger.error(e)
 
    await update.message.reply_text(
        f"✅ Hisob yuborildi: <b>{text}</b>\n@{rival_u} tasdiqlashini kuting.",
        parse_mode="HTML"
    )
 
    ctx.job_queue.run_once(
        ban_check_job,
        when=CONFIRM_MIN * 60,
        data={"mid": m["id"], "rival_id": rival_id, "submitter_id": uid}
    ) if ctx.job_queue else None
 
# ═══════════════════════════
# TASDIQLASH
# ═══════════════════════════
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
        top3 = get_top3_ids()
 
        if m["winner_id"] is None:
            for pid in [m["player1_id"], m["player2_id"]]:
                u = get_user(pid)
                if u:
                    db_patch("users", {
                        "points": u["points"] + DRAW_PTS,
                        "draws": u["draws"] + 1
                    }, f"?id=eq.{pid}")
            result = (f"🤝 <b>Durang!</b>\n"
                     f"@{m['p1_name']} {m['score']} @{m['p2_name']}\n"
                     f"Ikkalangiz +{DRAW_PTS} ball!")
        else:
            winner_id = m["winner_id"]
            loser_id = m["player2_id"] if winner_id == m["player1_id"] else m["player1_id"]
            wu = get_user(winner_id)
            lu = get_user(loser_id)
 
            # Top 3 bonus
            if loser_id in top3 and winner_id not in top3:
                w_pts = TOP3_WIN
                l_pts = TOP3_LOSS
                bonus_text = "🔥 TOP 3 ni yutdingiz! MEGA BONUS!"
            else:
                w_pts = WIN_PTS
                l_pts = LOSS_PTS
                bonus_text = ""
 
            if wu:
                db_patch("users", {
                    "points": wu["points"] + w_pts,
                    "wins": wu["wins"] + 1
                }, f"?id=eq.{winner_id}")
            if lu:
                db_patch("users", {
                    "points": max(0, lu["points"] - l_pts),
                    "losses": lu["losses"] + 1
                }, f"?id=eq.{loser_id}")
 
            wn = m["p1_name"] if winner_id == m["player1_id"] else m["p2_name"]
            ln = m["p2_name"] if winner_id == m["player1_id"] else m["p1_name"]
            result = (f"🏆 <b>Natija!</b>\n"
                     f"@{m['p1_name']} {m['score']} @{m['p2_name']}\n\n"
                     f"✅ @{wn} +{w_pts} ball\n"
                     f"❌ @{ln} -{l_pts} ball\n"
                     + (f"\n{bonus_text}" if bonus_text else ""))
 
        for pid in [m["player1_id"], m["player2_id"]]:
            try:
                await ctx.bot.send_message(pid, result, parse_mode="HTML")
            except:
                pass
        await q.message.edit_text(result, parse_mode="HTML")
 
    else:
        db_patch("matches", {
            "status": "pending", "score": None,
            "submitted_by": None, "winner_id": None
        }, f"?id=eq.{mid}")
        rival_id = m["player2_id"] if uid == m["player1_id"] else m["player1_id"]
        try:
            await ctx.bot.send_message(rival_id,
                "❌ Hisob rad etildi. Qayta kiriting.")
        except:
            pass
        await q.message.edit_text("❌ Hisob rad etildi.")
 
# ═══════════════════════════
# BAN CHECK JOB
# ═══════════════════════════
async def ban_check_job(ctx: ContextTypes.DEFAULT_TYPE):
    d = ctx.job.data
    res = db_get("matches", f"?id=eq.{d['mid']}&select=status")
    if not res or res[0]["status"] == "done":
        return
    ban_until = (now_uz() + timedelta(hours=BAN_HOURS)).isoformat()
    db_patch("users", {"ban_until": ban_until}, f"?id=eq.{d['rival_id']}")
    try:
        await ctx.bot.send_message(d["rival_id"],
            f"🚫 <b>{BAN_HOURS} soatlik ban!</b>\n{CONFIRM_MIN} daqiqa ichida tasdiqlamadingiz.",
            parse_mode="HTML")
        await ctx.bot.send_message(d["submitter_id"],
            "ℹ️ Raqibingiz tasdiqlamadi — ban oldi. O'yin avtomatik bekor.")
    except:
        pass
    db_patch("matches", {"status": "done"}, f"?id=eq.{d['mid']}")
 
# ═══════════════════════════
# CALLBACK
# ═══════════════════════════
async def callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()
 
    if q.data == "home":
        await cmd_start(update, ctx)
    elif q.data == "find_match":
        await find_match_cb(q, ctx)
    elif q.data == "enter_score":
        await enter_score_cb(q, ctx)
    elif q.data == "leave_queue":
        remove_from_queue(uid)
        await q.message.edit_text("✅ Navbatdan chiqdingiz.")
    elif q.data == "admin":
        await show_admin(q, uid, ctx)
    elif q.data == "admin_season_end":
        await end_season(q, ctx)
    elif q.data.startswith("confirm:"):
        mid = int(q.data.split(":")[1])
        await do_confirm(q, ctx, uid, mid, "yes")
    elif q.data.startswith("deny:"):
        mid = int(q.data.split(":")[1])
        await do_confirm(q, ctx, uid, mid, "no")
 
# ═══════════════════════════
# MESSAGE HANDLER
# ═══════════════════════════
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
 
    if ctx.user_data.get("score_match"):
        ctx.user_data.pop("score_match", None)
        await process_score(update, ctx, uid, text)
        return
 
    await update.message.reply_text(
        "Ilovani ochish uchun /start bosing.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏆 Ilovani ochish", web_app=WebAppInfo(url=WEBAPP_URL))
        ]])
    )
 
# ═══════════════════════════
# /hisob
# ═══════════════════════════
async def cmd_hisob(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    m = get_my_match(uid)
    if not m:
        await update.message.reply_text(
            "❗ Faol o'yin yo'q. Avval raqib toping!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⚡ Raqib qidirish", callback_data="find_match")
            ]])
        )
        return
    rival = m["p2_name"] if uid == m["player1_id"] else m["p1_name"]
    await update.message.reply_text(
        f"⚽ <b>Hisob kiritish</b>\n\nRaqib: <b>@{rival}</b>\n\n"
        f"Format: <code>siz-raqib</code>\nMisol: <code>3-1</code>",
        parse_mode="HTML"
    )
    ctx.user_data["score_match"] = True
 
# ═══════════════════════════
# ADMIN
# ═══════════════════════════
async def show_admin(q, uid, ctx):
    if uid != ADMIN_ID:
        await q.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    total   = len(db_get("users", "?select=id"))
    total_m = len(db_get("matches", "?select=id"))
    done_m  = len(db_get("matches", "?status=eq.done&select=id"))
    queue_n = len(db_get("queue", "?select=user_id"))
    status, info = get_season_status()
 
    await q.message.edit_text(
        f"👑 <b>ADMIN PANEL</b>\n\n"
        f"👥 Jami a'zolar: <b>{total}</b>\n"
        f"⚔️ Jami o'yinlar: <b>{total_m}</b>\n"
        f"✅ Tugallangan: <b>{done_m}</b>\n"
        f"⏳ Navbatda: <b>{queue_n}</b>\n\n"
        f"📅 Mavsum holati: <b>{status}</b> ({info})",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏁 Mavsumni tugatish", callback_data="admin_season_end")],
            [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="home")]
        ])
    )
 
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        return
    total   = len(db_get("users", "?select=id"))
    total_m = len(db_get("matches", "?select=id"))
    queue_n = len(db_get("queue", "?select=user_id"))
 
    await update.message.reply_text(
        f"👑 <b>ADMIN PANEL</b>\n\n"
        f"👥 Jami: <b>{total}</b>\n"
        f"⚔️ O'yinlar: <b>{total_m}</b>\n"
        f"⏳ Navbatda: <b>{queue_n}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏁 Mavsumni tugatish", callback_data="admin_season_end")
        ]])
    )
 
async def end_season(q, ctx):
    if q.from_user.id != ADMIN_ID:
        return
    top = db_get("users", "?order=points.desc&select=*&limit=3")
    if not top:
        await q.message.edit_text("❌ Foydalanuvchilar topilmadi.")
        return
 
    medals = ["🥇", "🥈", "🥉"]
    result = f"🏁 <b>1-MAVSUM TUGADI!</b>\n\n🏆 <b>G'OLIBLAR:</b>\n\n"
    for i, u in enumerate(top[:3]):
        result += f"{medals[i]} @{u['username']} — {u['points']} ball\n"
 
    users = db_get("users", "?select=id")
    for u in users:
        try:
            await ctx.bot.send_message(u["id"], result, parse_mode="HTML")
        except:
            pass
 
    await q.message.edit_text(result + "\n\n✅ Barcha foydalanuvchilarga yuborildi.", parse_mode="HTML")
 
# ═══════════════════════════
# POST INIT
# ═══════════════════════════
async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "Botni ishga tushirish"),
        BotCommand("hisob", "Hisob kiritish"),
        BotCommand("admin", "Admin panel"),
    ])
 
# ═══════════════════════════
# MAIN
# ═══════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("hisob", cmd_hisob))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("✅ Zico World Liga v2 ishga tushdi!")
    app.run_polling(allowed_updates=["message", "callback_query"])
 
if __name__ == "__main__":
    main()
