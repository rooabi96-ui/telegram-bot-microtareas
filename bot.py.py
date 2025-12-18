import os
import asyncio
from datetime import datetime, timezone, date
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import psycopg
from psycopg.rows import dict_row

# ========================
# CONFIG (Railway Variables)
# ========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
async def whoami(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        f"🆔 Tu ID: {uid}\n"
        f"👑 Admin: {'SI' if is_admin(uid) else 'NO'}\n"
        f"ADMIN_IDS cargados: {sorted(list(ADMIN_IDS))}"
    )

if not BOT_TOKEN or not DATABASE_URL:
    raise RuntimeError("Faltan variables en Railway")

# ========================
# HELPERS
# ========================
def db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def usd(c): return f"${c/100:.2f} USD"
def now(): return datetime.now(timezone.utc)
def today(): return date.today()

# ========================
# INIT DB
# ========================
def init_db():
    with db() as c, c.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS campaigns(
            id SERIAL PRIMARY KEY,
            name TEXT,
            budget INT,
            spent INT DEFAULT 0,
            active BOOLEAN DEFAULT TRUE
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks(
            id SERIAL PRIMARY KEY,
            campaign_id INT,
            title TEXT,
            prompt TEXT,
            reward INT,
            active BOOLEAN DEFAULT TRUE
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            tg_id BIGINT PRIMARY KEY,
            balance INT DEFAULT 0
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS subs(
            id SERIAL PRIMARY KEY,
            tg_id BIGINT,
            task_id INT,
            answer TEXT,
            status TEXT DEFAULT 'pending'
        );
        """)
        c.commit()

# ========================
# USER COMMANDS
# ========================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with db() as c, c.cursor() as cur:
        cur.execute("INSERT INTO users(tg_id) VALUES(%s) ON CONFLICT DO NOTHING", (uid,))
        c.commit()
    await update.message.reply_text(
        "👋 Bienvenida\n"
        "Acá ganás centavos USD con tareas reales.\n\n"
        "Usá /task para empezar\n"
        "Usá /balance para ver tu saldo"
    )
         "✅ Build 18-12\n"


async def balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with db() as c, c.cursor() as cur:
        cur.execute("SELECT balance FROM users WHERE tg_id=%s", (uid,))
        b = cur.fetchone()["balance"]
    await update.message.reply_text(f"💰 Tu saldo: {usd(b)}")

async def task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with db() as c, c.cursor() as cur:
        cur.execute("""
        SELECT t.* FROM tasks t
        JOIN campaigns c ON c.id=t.campaign_id
        WHERE t.active AND c.active
        LIMIT 1
        """)
        t = cur.fetchone()
    if not t:
        await update.message.reply_text("No hay tareas disponibles.")
        return
    ctx.user_data["task_id"] = t["id"]
    await update.message.reply_text(
        f"🧩 {t['title']}\n{t['prompt']}\n\n"
        "Respondé con:\n/answer TU_RESPUESTA"
    )

async def answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    tid = ctx.user_data.get("task_id")
    if not tid:
        await update.message.reply_text("Pedí una tarea primero.")
        return
    ans = update.message.text.split(" ",1)[1]
    with db() as c, c.cursor() as cur:
        cur.execute("INSERT INTO subs(tg_id,task_id,answer) VALUES(%s,%s,%s)", (uid,tid,ans))
        c.commit()
    await update.message.reply_text("🕵️ En revisión")

# ========================
# ADMIN COMMANDS
# ========================
def is_admin(uid): return uid in ADMIN_IDS

async def newcampaign(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    _, name, budget = update.message.text.split("|")
    with db() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO campaigns(name,budget) VALUES(%s,%s)",
            (name.strip(), int(budget.strip()))
        )
        c.commit()
    await update.message.reply_text("✅ Campaña creada")

async def addtask(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    _, cid, title, reward, prompt = update.message.text.split("|")
    with db() as c, c.cursor() as cur:
        cur.execute(
            "INSERT INTO tasks(campaign_id,title,reward,prompt) VALUES(%s,%s,%s,%s)",
            (int(cid), title.strip(), int(reward), prompt.strip())
        )
        c.commit()
    await update.message.reply_text("✅ Tarea creada")

async def approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    sid = int(update.message.text.split()[1])
    with db() as c, c.cursor() as cur:
        cur.execute("""
        SELECT s.tg_id, t.reward, c.id cid, c.budget, c.spent
        FROM subs s
        JOIN tasks t ON t.id=s.task_id
        JOIN campaigns c ON c.id=t.campaign_id
        WHERE s.id=%s
        """, (sid,))
        r = cur.fetchone()
        if r["spent"] + r["reward"] > r["budget"]:
            cur.execute("UPDATE campaigns SET active=false WHERE id=%s", (r["cid"],))
        else:
            cur.execute("UPDATE users SET balance=balance+%s WHERE tg_id=%s", (r["reward"], r["tg_id"]))
            cur.execute("UPDATE campaigns SET spent=spent+%s WHERE id=%s", (r["reward"], r["cid"]))
            cur.execute("UPDATE subs SET status='approved' WHERE id=%s", (sid,))
        c.commit()
    await update.message.reply_text("✅ Procesado")

# ========================
# MAIN
# ========================
async def on_startup(app): await asyncio.to_thread(init_db)

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("task", task))
    app.add_handler(CommandHandler("answer", answer))
    app.add_handler(CommandHandler("newcampaign", newcampaign))
    app.add_handler(CommandHandler("addtask", addtask))
    app.add_handler(CommandHandler("approve", approve))
app.add_handler(CommandHandler("whoami", whoami))
    app.run_polling()

if __name__ == "__main__":
    main()
