from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8512517350:AAE9qK9mrM0_T0GKp39PRf0VT8kWfh1q5w8"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hola!\n"
        "Soy un bot de micro-tareas.\n\n"
        "Comandos disponibles:\n"
        "/task - recibir una tarea\n"
        "/balance - ver saldo"
    )

async def task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pending"] = True
    await update.message.reply_text(
        "🧩 Tarea de prueba\n"
        "Respondé escribiendo exactamente:\n"
        "OK\n\n"
        "Usá: /answer OK"
    )

async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("pending"):
        await update.message.reply_text("Primero pedí una tarea con /task")
        return

    parts = update.message.text.split(" ", 1)
    if len(parts) < 2:
        await update.message.reply_text("Usá: /answer OK")
        return

    if parts[1].strip().upper() == "OK":
        context.user_data["pending"] = False
        context.user_data["balance"] = context.user_data.get("balance", 0) + 2
        await update.message.reply_text("✅ Correcto. Sumaste 2 centavos.")
    else:
        await update.message.reply_text("❌ Incorrecto. Probá otra vez.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal = context.user_data.get("balance", 0)
    await update.message.reply_text(f"💰 Tu saldo: {bal} centavos.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("task", task))
    app.add_handler(CommandHandler("answer", answer))
    app.add_handler(CommandHandler("balance", balance))
    app.run_polling()

if __name__ == "__main__":
    main()
