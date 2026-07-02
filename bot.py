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
WIN_PTS=15; LOSS_PTS=10; DRAW_PTS=5; BAN_DAYS=3; CONFIRM_MIN=5
 
SB="https://wfpspsiikwdxmatavwwm.supabase.co"
SK="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndmcHNwc2lpa3dkeG1hdGF2d3dtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI4MjYwMTcsImV4cCI6MjA5ODQwMjAxN30.a48U3deN-0Kjg3FC4Edy-m3Z71ru-LyHuohkFwkEyfw"
H={"apikey":SK,"Authorization":f"Bearer {SK}","Content-Type":"application/json","Prefer":"resolution=merge-duplicates,return=representation"}
 
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s",level=logging.INFO)
log=logging.getLogger(__name__)
 
def now(): return datetime.now(UZ)
def today(): return now().strftime("%Y-%m-%d")
def g(t,p=""): r=requests.get(f"{SB}/rest/v1/{t}{p}",headers=H); return r.json() if r.ok else []
def po(t,d): r=requests.post(f"{SB}/rest/v1/{t}",headers=H,json=d); return r.json() if r.ok else None
def pa(t,d,p): return requests.patch(f"{SB}/rest/v1/{t}{p}",headers=H,json=d).ok
def de(t,p): return requests.delete(f"{SB}/rest/v1/{t}{p}",headers=H).ok
 
def get_user(uid): r=g("users",f"?id=eq.{uid}"); return r[0] if r else None
def save_user(user,photo=None):
    d={"id":user.id,"username":user.username or user.first_name,"first_name":user.first_name or ""}
    if photo: d["photo_url"]=photo
    po("users",d)
 
def is_banned(uid):
    u=get_user(uid)
    if u and u.get("ban_until"):
        try:
            bd=datetime.fromisoformat(u["ban_until"].replace("Z","+00:00"))
            if now()<bd: return True,bd
            pa("users",{"ban_until":None},f"?id=eq.{uid}")
        except: pass
    return False,None
 
def is_maintenance():
    r=g("maintenance","?id=eq.1"); return r[0]["active"] if r else False
 
def get_season():
    r=g("seasons","?order=id.desc&limit=1"); return r[0] if r else {"id":1,"status":"active"}
 
def get_my_match(uid):
    r=g("matches",f"?or=(player1_id.eq.{uid},player2_id.eq.{uid})&status=neq.done&order=id.desc&limit=1")
    if not r: return None
    m=r[0]; p1=get_user(m["player1_id"]); p2=get_user(m["player2_id"])
    m["p1n"]=p1["username"] if p1 else "?"; m["p2n"]=p2["username"] if p2 else "?"
    return m
 
def is_registered(uid,snum):
    r=g("registrations",f"?user_id=eq.{uid}&season_num=eq.{snum}"); return len(r)>0
 
SEASON_START_DT = datetime(2026, 7, 3, 7, 0, 0, tzinfo=ZoneInfo("Asia/Tashkent"))
 
def season_start_text():
    return "🗓️ <b>1-mavsum 03.07.2026 soat 07:00 da ishlaydi!</b>"
 
async def broadcast_to_all(bot, text, kb=None):
    """Barcha foydalanuvchilarga xabar yuborish"""
    users=g("users","?select=id")
    for u in users:
        try: await bot.send_message(u["id"],text,parse_mode="HTML",reply_markup=kb)
        except: pass
 
async def cmd_start(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    try:
        photos=await ctx.bot.get_user_profile_photos(user.id,limit=1)
        photo=None
        if photos.total_count>0:
            f=await ctx.bot.get_file(photos.photos[0][-1].file_id)
            photo=f"https://api.telegram.org/file/bot{BOT_TOKEN}/{f.file_path}"
        save_user(user,photo)
    except: save_user(user)
 
    # Texnik ish
    if is_maintenance():
        text=("🔧 <b>Texnik ishlar olib borilmoqda</b>\n\n"
              "Iltimos <b>soat 13:00</b> yoki <b>15:30</b> gacha kuting.\n\n"
              "Rating va profil ko'rish mumkin ⬇️")
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("🏆 Ilovani ochish",web_app=WebAppInfo(url=WEBAPP_URL))]])
        if update.message: await update.message.reply_text(text,parse_mode="HTML",reply_markup=kb)
        else:
            try: await update.callback_query.message.edit_text(text,parse_mode="HTML",reply_markup=kb)
            except: pass
        return
 
    season=get_season()
    snum=season["id"]
    s_status=season.get("status","active")
 
    # Mavsum tugagan — admin yangi boshlagunicha
    if s_status=="ended":
        text=("🔧 <b>Texnik ishlar olib borilmoqda</b>\n\n"
              "Iltimos <b>soat 13:00</b> yoki <b>15:30</b> gacha kuting.\n\n"
              "Rating va profil ko'rish mumkin ⬇️")
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("🏆 Ilovani ochish",web_app=WebAppInfo(url=WEBAPP_URL))]])
        if user.id==ADMIN_ID:
            kb=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Yangi mavsum boshlash",callback_data="admin_new_season")],
                [InlineKeyboardButton("🏆 Ilovani ochish",web_app=WebAppInfo(url=WEBAPP_URL))]
            ])
        if update.message: await update.message.reply_text(text,parse_mode="HTML",reply_markup=kb)
        else:
            try: await update.callback_query.message.edit_text(text,parse_mode="HTML",reply_markup=kb)
            except: pass
        return
 
    banned,ban_dt=is_banned(user.id)
    m=get_my_match(user.id)
    registered=is_registered(user.id,snum)
 
    if banned:
        end=ban_dt.strftime('%d.%m.%Y %H:%M')
        text=(f"👋 <b>Salom, {user.first_name}!</b>\n\n"
              f"🚫 <b>{BAN_DAYS} kunlik ban!</b>\n📅 Tugaydi: {end}\n\n"
              f"Rating va ilovani ko'rishingiz mumkin.")
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("🏆 Ilovani ochish",web_app=WebAppInfo(url=WEBAPP_URL))]])
    else:
        match_txt=""
        if m:
            rival=m["p2n"] if user.id==m["player1_id"] else m["p1n"]
            match_txt=f"\n\n⚔️ <b>Joriy o'yin:</b> @{rival}"
 
        n=now()
        if n < SEASON_START_DT:
            s_txt = season_start_text()
        else:
            s_txt = f"🟢 <b>{snum}-mavsum</b> faol"
 
        text=(f"👋 <b>Salom, {user.first_name}!</b>\n\n"
              f"🏆 <b>ZICO WORLD LIGA</b>\n"
              f"{s_txt}{match_txt}\n\n"
              f"⬇️ Ilovani oching!")
 
        buttons=[[InlineKeyboardButton("🏆 Ilovani ochish",web_app=WebAppInfo(url=WEBAPP_URL))]]
        if m: buttons.insert(0,[InlineKeyboardButton("⚽ Hisob kiritish",callback_data="enter_score")])
        if user.id==ADMIN_ID: buttons.append([InlineKeyboardButton("👑 Admin",callback_data="admin")])
        kb=InlineKeyboardMarkup(buttons)
 
    if update.message: await update.message.reply_text(text,parse_mode="HTML",reply_markup=kb)
    else:
        try: await update.callback_query.message.edit_text(text,parse_mode="HTML",reply_markup=kb)
        except: pass
 
async def accept_cb(q,ctx,seeker_id):
    rival_id=q.from_user.id
    rival=get_user(rival_id); seeker=get_user(seeker_id)
    if not rival or not seeker: await q.answer("❌ Xato",show_alert=True); return
    banned,ban_dt=is_banned(rival_id)
    if banned: await q.answer(f"🚫 {ban_dt.strftime('%d.%m')} gacha bansiz!",show_alert=True); return
    season=get_season(); snum=season["id"]
    res=po("matches",{"player1_id":seeker_id,"player2_id":rival_id,"season_num":snum,
        "season_date":today(),"deadline":(now()+timedelta(hours=24)).isoformat()})
    s_name=seeker["username"]; r_name=rival["username"]
    msg=(f"✅ <b>O'yin boshlandi!</b>\n\n"
         f"👤 @{s_name}  🆚  👤 @{r_name}\n\n"
         f"🎮 <b>eFootball 1vs1</b>\n\n"
         f"📌 <b>Telegram ID lar:</b>\n"
         f"@{s_name}: <code>{seeker_id}</code>\n"
         f"@{r_name}: <code>{rival_id}</code>\n\n"
         f"G'olib hisob yozadi: /hisob\n"
         f"⚠️ <b>{CONFIRM_MIN} daqiqada tasdiqlanmasa → {BAN_DAYS} kunlik ban!</b>")
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("⚽ Hisob kiritish",callback_data="enter_score"),
        InlineKeyboardButton("🏆 Ilova",web_app=WebAppInfo(url=WEBAPP_URL))]])
    try: await ctx.bot.send_message(seeker_id,msg,parse_mode="HTML",reply_markup=kb)
    except: pass
    await q.message.edit_text(msg,parse_mode="HTML",reply_markup=kb)
 
async def decline_cb(q,ctx,seeker_id):
    rival=get_user(q.from_user.id); rn=rival["username"] if rival else "?"
    try:
        await ctx.bot.send_message(seeker_id,f"❌ @{rn} taklifni rad etdi.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏆 Ilovani ochish",web_app=WebAppInfo(url=WEBAPP_URL))]]))
    except: pass
    await q.message.edit_text("❌ Taklifni rad etdingiz.")
 
async def enter_score_cb(q,ctx):
    uid=q.from_user.id; m=get_my_match(uid)
    if not m: await q.answer("❗ Faol o'yin yo'q!",show_alert=True); return
    rival=m["p2n"] if uid==m["player1_id"] else m["p1n"]
    await q.message.reply_text(f"⚽ <b>Hisob kiritish</b>\nRaqib: <b>@{rival}</b>\nFormat: <code>3-1</code>",parse_mode="HTML")
    ctx.user_data["sm"]=True
 
async def cmd_hisob(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id; m=get_my_match(uid)
    if not m: await update.message.reply_text("❗ Faol o'yin yo'q!"); return
    rival=m["p2n"] if uid==m["player1_id"] else m["p1n"]
    await update.message.reply_text(f"⚽ <b>Hisob kiritish</b>\nRaqib: <b>@{rival}</b>\nFormat: <code>3-1</code>",parse_mode="HTML")
    ctx.user_data["sm"]=True
 
async def process_score(update,ctx,uid,text):
    parts=text.split("-")
    if len(parts)!=2 or not parts[0].strip().isdigit() or not parts[1].strip().isdigit():
        await update.message.reply_text("❗ Format: <code>3-1</code>",parse_mode="HTML")
        ctx.user_data["sm"]=True; return
    m=get_my_match(uid)
    if not m: await update.message.reply_text("❗ Faol o'yin yo'q."); return
    if m.get("status")=="awaiting": await update.message.reply_text("⏳ Raqib tasdiqlasin."); return
    g1,g2=int(parts[0].strip()),int(parts[1].strip())
    rival_id=m["player2_id"] if uid==m["player1_id"] else m["player1_id"]
    rival_u=m["p2n"] if uid==m["player1_id"] else m["p1n"]
    my_u=update.effective_user.username or update.effective_user.first_name
    winner_id=uid if g1>g2 else (rival_id if g2>g1 else None)
    pa("matches",{"score":f"{g1}-{g2}","submitted_by":uid,"winner_id":winner_id,
        "submitted_at":now().isoformat(),"status":"awaiting"},f"?id=eq.{m['id']}")
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("✅ To'g'ri",callback_data=f"confirm:{m['id']}"),
        InlineKeyboardButton("❌ Xato",callback_data=f"deny:{m['id']}")]])
    try:
        await ctx.bot.send_message(rival_id,
            f"⚽ <b>Hisob tasdiqlash!</b>\n@{my_u} yubordi: <b>{g1}-{g2}</b>\nTo'g'rimi?\n"
            f"⚠️ <b>{CONFIRM_MIN} daqiqa ichida tasdiqlamasangiz → {BAN_DAYS} kunlik ban!</b>",
            parse_mode="HTML",reply_markup=kb)
    except Exception as e: log.error(e)
    await update.message.reply_text(f"✅ Hisob yuborildi: <b>{g1}-{g2}</b>",parse_mode="HTML")
    if ctx.job_queue:
        ctx.job_queue.run_once(confirm_timeout,when=CONFIRM_MIN*60,
            data={"mid":m["id"],"rival_id":rival_id,"submitter_id":uid,"rival_name":rival_u,"submitter_name":my_u})
 
async def confirm_timeout(ctx):
    d=ctx.job.data
    r=g("matches",f"?id=eq.{d['mid']}&select=status")
    if not r or r[0]["status"]=="done": return
    bu=(now()+timedelta(days=BAN_DAYS)).isoformat()
    pa("users",{"ban_until":bu},f"?id=eq.{d['rival_id']}")
    pa("matches",{"status":"done"},f"?id=eq.{d['mid']}")
    end=(now()+timedelta(days=BAN_DAYS)).strftime('%d.%m.%Y %H:%M')
    try:
        await ctx.bot.send_message(d["rival_id"],
            f"🚫 <b>{BAN_DAYS} kunlik ban!</b>\n@{d['submitter_name']} hisob yozdi,\n"
            f"siz {CONFIRM_MIN} daqiqa ichida tasdiqlamadingiz.\n📅 Ban tugaydi: {end}",parse_mode="HTML")
    except: pass
    try:
        await ctx.bot.send_message(d["submitter_id"],
            f"ℹ️ @{d['rival_name']} tasdiqlamadi → {BAN_DAYS} kunlik ban oldi.")
    except: pass
 
async def do_confirm(q,ctx,uid,mid,action):
    r=g("matches",f"?id=eq.{mid}")
    if not r: await q.message.edit_text("✅ Tugallangan."); return
    m=r[0]
    if m["status"]=="done": await q.message.edit_text("✅ Allaqachon tugallangan."); return
    if uid==m.get("submitted_by"): await q.answer("❌ O'z hisobingizni tasdiqlay olmaysiz!",show_alert=True); return
    p1=get_user(m["player1_id"]); p2=get_user(m["player2_id"])
    p1n=p1["username"] if p1 else "?"; p2n=p2["username"] if p2 else "?"
    if action=="yes":
        pa("matches",{"status":"done","confirmed":1},f"?id=eq.{mid}")
        wid=m.get("winner_id")
        if wid is None:
            for pid in [m["player1_id"],m["player2_id"]]:
                u=get_user(pid)
                if u: pa("users",{"points":u["points"]+DRAW_PTS,"draws":u["draws"]+1},f"?id=eq.{pid}")
            result=f"🤝 <b>Durang!</b>\n@{p1n} {m['score']} @{p2n}\nIkkalangiz +{DRAW_PTS} ball!"
        else:
            lid=m["player2_id"] if wid==m["player1_id"] else m["player1_id"]
            wu=get_user(wid); lu=get_user(lid)
            if wu: pa("users",{"points":wu["points"]+WIN_PTS,"wins":wu["wins"]+1},f"?id=eq.{wid}")
            if lu: pa("users",{"points":max(0,lu["points"]-LOSS_PTS),"losses":lu["losses"]+1},f"?id=eq.{lid}")
            wn=p1n if wid==m["player1_id"] else p2n; ln=p2n if wid==m["player1_id"] else p1n
            result=f"🏆 <b>Natija!</b>\n@{p1n} {m['score']} @{p2n}\n✅ @{wn} +{WIN_PTS} ball\n❌ @{ln} -{LOSS_PTS} ball"
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("🏆 Ilovani ochish",web_app=WebAppInfo(url=WEBAPP_URL))]])
        for pid in [m["player1_id"],m["player2_id"]]:
            try: await ctx.bot.send_message(pid,result,parse_mode="HTML",reply_markup=kb)
            except: pass
        await q.message.edit_text(result,parse_mode="HTML")
    else:
        pa("matches",{"status":"pending","score":None,"submitted_by":None,"winner_id":None},f"?id=eq.{mid}")
        sid=m.get("submitted_by")
        try: await ctx.bot.send_message(sid,"❌ Hisob rad etildi. Qayta kiriting: /hisob")
        except: pass
        await q.message.edit_text("❌ Hisob rad etildi.")
 
async def show_admin(q,uid,ctx):
    if uid!=ADMIN_ID: await q.answer("❌",show_alert=True); return
    total=len(g("users","?select=id")); tm=len(g("matches","?select=id"))
    dm=len(g("matches","?status=eq.done&select=id")); qn=len(g("queue","?select=user_id"))
    season=get_season(); mn=g("maintenance","?id=eq.1")
    mint=mn[0]["active"] if mn else False
    await q.message.edit_text(
        f"👑 <b>ADMIN — {season['id']}-MAVSUM</b>\n\n"
        f"👥 A'zolar: <b>{total}</b>\n⚔️ O'yinlar: <b>{tm}</b>\n"
        f"✅ Tugallangan: <b>{dm}</b>\n⏳ Navbatda: <b>{qn}</b>\n"
        f"🔧 Texnik ish: <b>{'FAOL' if mint else 'off'}</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏁 Mavsumni yakunlash",callback_data="admin_end_season")],
            [InlineKeyboardButton("🔧 Texnik ish ON/OFF",callback_data="admin_toggle_maint")],
            [InlineKeyboardButton("🕵️ Shubhalilarni tekshir",callback_data="admin_check_cheats")],
            [InlineKeyboardButton("🏠 Bosh sahifa",callback_data="home")]
        ]))
 
async def cmd_admin(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    if uid!=ADMIN_ID: return
    season=get_season(); total=len(g("users","?select=id")); qn=len(g("queue","?select=user_id"))
    await update.message.reply_text(
        f"👑 <b>ADMIN — {season['id']}-MAVSUM</b>\n👥 {total} a'zo · ⏳ {qn} navbatda",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏁 Mavsumni yakunlash",callback_data="admin_end_season")],
            [InlineKeyboardButton("🔧 Texnik ish ON/OFF",callback_data="admin_toggle_maint")],
            [InlineKeyboardButton("🕵️ Shubhalilarni tekshir",callback_data="admin_check_cheats")]
        ]))
 
async def maintenance_job(ctx):
    """Har chorshanba 07:00 — texnik ish boshlash"""
    pa("maintenance",{"active":True,"started_at":now().isoformat()},"?id=eq.1")
    users=g("users","?select=id")
    for u in users:
        try:
            await ctx.bot.send_message(u["id"],
                "🔧 <b>Texnik ishlar boshlanmoqda</b>\n\n"
                "Har haftali tekshiruv o'tkazilmoqda.\n"
                "Iltimos <b>11:30</b> gacha kuting.",parse_mode="HTML")
        except: pass
 
async def maintenance_end_job(ctx):
    """Har chorshanba 11:30 — texnik ish tugatish"""
    pa("maintenance",{"active":False},"?id=eq.1")
    # Shubhalilarni tekshirish
    suspicious=await check_suspicious(ctx)
    users=g("users","?select=id")
    for u in users:
        try:
            await ctx.bot.send_message(u["id"],
                "✅ <b>Texnik ishlar tugadi!</b>\n\nO'yin davom etadi. 🎮",parse_mode="HTML")
        except: pass
 
async def monthly_reset_job(ctx):
    """Har oyda bir rating reset + yangi mavsum"""
    season=get_season(); new_snum=season["id"]+1
    pa("seasons",{"status":"ended","ended_at":now().isoformat()},f"?id=eq.{season['id']}")
    # Yangi mavsum avto-boshlash
    po("seasons",{"id":new_snum,"status":"active","started_at":now().isoformat()})
    # Reset
    requests.patch(f"{SB}/rest/v1/users?id=gt.0",headers=H,json={"points":0,"wins":0,"draws":0,"losses":0})
    de("queue","?id=gt.0")
    users=g("users","?select=id")
    top=g("users","?order=points.desc&select=*&limit=3")
    medals=["🥇","🥈","🥉"]; result=f"🏆 <b>{season['id']}-MAVSUM TUGADI!</b>\n\n"
    for i,u in enumerate(top[:3]): result+=f"{medals[i]} @{u['username']} — {u['points']} ball\n"
    result+=f"\n\n🆕 <b>{new_snum}-mavsum boshlandi!</b>\nBarcha ratinglar yangilandi."
    for u in users:
        try: await ctx.bot.send_message(u["id"],result,parse_mode="HTML")
        except: pass
 
async def check_suspicious(ctx):
    """Shubhali natijalarni tekshirish (10+ farqli hisoblar)"""
    matches=g("matches","?status=eq.done&select=*&order=id.desc&limit=100")
    suspicious=[]
    for m in matches:
        if m.get("score"):
            try:
                parts=m["score"].split("-")
                if len(parts)==2:
                    diff=abs(int(parts[0])-int(parts[1]))
                    if diff>=8:
                        p1=get_user(m["player1_id"]); p2=get_user(m["player2_id"])
                        suspicious.append(f"⚠️ {m['score']} — @{p1['username'] if p1 else '?'} vs @{p2['username'] if p2 else '?'}")
            except: pass
    if suspicious:
        msg="🕵️ <b>Shubhali natijalar:</b>\n\n"+"\n".join(suspicious[:20])
        try: await ctx.bot.send_message(ADMIN_ID,msg,parse_mode="HTML")
        except: pass
    return suspicious
 
async def callback(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; uid=q.from_user.id; await q.answer(); d=q.data
    if d=="home": await cmd_start(update,ctx)
    elif d=="enter_score": await enter_score_cb(q,ctx)
    elif d.startswith("accept:"): await accept_cb(q,ctx,int(d.split(":")[1]))
    elif d.startswith("decline:"): await decline_cb(q,ctx,int(d.split(":")[1]))
    elif d.startswith("confirm:"): await do_confirm(q,ctx,uid,int(d.split(":")[1]),"yes")
    elif d.startswith("deny:"): await do_confirm(q,ctx,uid,int(d.split(":")[1]),"no")
    elif d=="admin": await show_admin(q,uid,ctx)
    elif d=="admin_end_season":
        if uid!=ADMIN_ID: return
        season=get_season()
        pa("seasons",{"status":"ended","ended_at":now().isoformat()},f"?id=eq.{season['id']}")
        top=g("users","?order=points.desc&select=*&limit=3")
        medals=["🥇","🥈","🥉"]; result=f"🏁 <b>{season['id']}-MAVSUM YAKUNLANDI!</b>\n\n🏆 <b>G'OLIBLAR:</b>\n\n"
        for i,u in enumerate(top[:3]): result+=f"{medals[i]} @{u['username']} — {u['points']} ball\n"
        result+="\n\n🔧 Texnik ishlar boshlanmoqda...\nIltimos kuting."
        users=g("users","?select=id")
        for u in users:
            try: await ctx.bot.send_message(u["id"],result,parse_mode="HTML")
            except: pass
        await q.message.edit_text(result+"\n\n✅ Barcha foydalanuvchilarga yuborildi.\n\n<b>Yangi mavsum boshlash uchun tugmani bosing:</b>",
            parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Yangi mavsum boshlash",callback_data="admin_new_season")]]))
    elif d=="admin_new_season":
        if uid!=ADMIN_ID: return
        season=get_season(); new_snum=season["id"]+1
        po("seasons",{"id":new_snum,"status":"active","started_at":now().isoformat()})
        requests.patch(f"{SB}/rest/v1/users?id=gt.0",headers=H,json={"points":0,"wins":0,"draws":0,"losses":0})
        de("queue","?id=gt.0")
        users=g("users","?select=id")
        for u in users:
            try:
                await ctx.bot.send_message(u["id"],
                    f"🚀 <b>{new_snum}-MAVSUM BOSHLANDI!</b>\n\nBarcha ratinglar yangilandi.\nO'yin boshlang! 🎮",
                    parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏆 Ilovani ochish",web_app=WebAppInfo(url=WEBAPP_URL))]]))
            except: pass
        await q.message.edit_text(f"✅ {new_snum}-mavsum boshlandi!",parse_mode="HTML")
    elif d=="admin_toggle_maint":
        if uid!=ADMIN_ID: return
        mn=g("maintenance","?id=eq.1"); cur=mn[0]["active"] if mn else False
        new_val=not cur
        pa("maintenance",{"active":new_val,"started_at":now().isoformat() if new_val else None},"?id=eq.1")
        # Barcha foydalanuvchilarga xabar yuborish
        if new_val:
            msg=("🔧 <b>Texnik ishlar boshlanmoqda!</b>\n\n"
                 "Iltimos <b>soat 13:00</b> yoki <b>15:30</b> gacha kuting.\n\n"
                 "Rating va profil ko'rish mumkin ⬇️")
        else:
            msg=("✅ <b>Texnik ishlar tugadi!</b>\n\n"
                 "O'yin davom etadi. Ilovani oching! 🎮")
        kb_broad=InlineKeyboardMarkup([[InlineKeyboardButton("🏆 Ilovani ochish",web_app=WebAppInfo(url=WEBAPP_URL))]])
        users=g("users","?select=id")
        for u2 in users:
            try: await ctx.bot.send_message(u2["id"],msg,parse_mode="HTML",reply_markup=kb_broad)
            except: pass
        await q.answer(f"🔧 Texnik ish: {'ON' if new_val else 'OFF'} — Barcha foydalanuvchilarga yuborildi!",show_alert=True)
        await show_admin(q,uid,ctx)
    elif d=="admin_check_cheats":
        if uid!=ADMIN_ID: return
        susp=await check_suspicious(ctx)
        if susp: await q.answer(f"⚠️ {len(susp)} shubhali natija topildi!",show_alert=True)
        else: await q.answer("✅ Shubhali natija yo'q",show_alert=True)
 
async def handle_message(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id; text=update.message.text.strip()
    if ctx.user_data.get("sm"):
        ctx.user_data.pop("sm",None); await process_score(update,ctx,uid,text); return
    await update.message.reply_text("Botdan foydalanish: /start",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Start",callback_data="home")]]))
 
async def post_init(app:Application):
    await app.bot.set_my_commands([
        BotCommand("start","Bosh menyu"),BotCommand("hisob","Hisob kiritish"),BotCommand("admin","Admin")])
    # Har chorshanba 07:00 texnik ish ON
    app.job_queue.run_daily(maintenance_job,time=datetime.now(UZ).replace(hour=7,minute=0,second=0).timetz(),days=(2,))
    # Har chorshanba 11:30 texnik ish OFF
    app.job_queue.run_daily(maintenance_end_job,time=datetime.now(UZ).replace(hour=11,minute=30,second=0).timetz(),days=(2,))
 
def main():
    app=Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start",cmd_start))
    app.add_handler(CommandHandler("hisob",cmd_hisob))
    app.add_handler(CommandHandler("admin",cmd_admin))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,handle_message))
    log.info("✅ Zico World Liga FINAL v4 ishga tushdi!")
    app.run_polling(allowed_updates=["message","callback_query"])
 
if __name__=="__main__": main()