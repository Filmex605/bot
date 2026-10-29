import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask, request, jsonify

# Configuração de logs
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Token e Configurações
TOKEN = "9156028501:AAGO9cUk8dCTdfdYGCkREdv0mYRn8ZQ_koU"
PORT = int(os.environ.get("PORT", "10000"))
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")

# Inicializa o Flask e a Aplicação do Telegram
app = Flask(__name__)
telegram_app = None

# 1. Comando /start no Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    keyboard = [
        [InlineKeyboardButton("⭐ Conhecer o Filmex", callback_data="plano_vip")],
        [InlineKeyboardButton("💬 Falar com o Suporte", url="https://t.me/Filmex_Grupo")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Olá, {user_name} 🍿.\n\n"
        "Participe do nosso grupo para ter acesso liberado ao canal de filmes e séries!",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# 2. Cliques nos botões do Telegram
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "plano_vip":
        link_kiwify = "https://pay.kiwify.com.br/cGoSyA8"
        
        keyboard = [
            [InlineKeyboardButton("💳 Pagar Assinatura (Kiwify)", url=link_kiwify)],
            [InlineKeyboardButton("🔙 Voltar", callback_data="voltar_inicio")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text="👑 **Filmex - Plano Mensal**\n\n"
                 "✅ Acesso ilimitado ao canal fechado\n"
                 "💰 **Valor:** R$ 9,90/mês",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif query.data == "voltar_inicio":
        keyboard = [
            [InlineKeyboardButton("⭐ Conhecer grupo Filmex", callback_data="plano_vip")],
            [InlineKeyboardButton("💬 Falar com o Suporte", url="https://t.me/Filmex_Grupo")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Escolha uma opção:", reply_markup=reply_markup)

# 3. Rota principal que recebe as mensagens do Telegram via Webhook
@app.route(f'/{TOKEN}', methods=['POST'])
def telegram_webhook():
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, telegram_app.bot)
    asyncio.run(telegram_app.process_update(update))
    return jsonify({"status": "ok"}), 200

# 4. Rota de Ping (Anti-Sleep)
@app.route('/ping', methods=['GET'])
def ping_server():
    return "Pong! Servidor ativo.", 200

# 5. Rota de Pagamento da Kiwify
@app.route('/webhook-kiwify', methods=['POST'])
def webhook_kiwify():
    dados = request.json
    try:
        status = dados.get("status") or dados.get("order_status")
        if status == "paid" or status == "approved":
            pass
        return jsonify({"status": "recebido"}), 200
    except Exception as e:
        logging.error(f"Erro no webhook Kiwify: {e}")
        return jsonify({"status": "erro"}), 500

@app.route('/')
def home():
    return "Filmex rodando!"

async def setup_bot():
    global telegram_app
    telegram_app = Application.builder().token(TOKEN).build()

    telegram_app.add_handler(CommandHandler('start', start))
    telegram_app.add_handler(CallbackQueryHandler(button_handler))

    await telegram_app.initialize()
    
    # Configura automaticamente o Webhook do Telegram no Render
    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/{TOKEN}"
        await telegram_app.bot.set_webhook(url=webhook_url)
        logging.info(f"Webhook configurado com sucesso para: {webhook_url}")

    await telegram_app.start()

if __name__ == '__main__':
    # Inicializa o bot e o webhook do Telegram antes de subir o servidor Flask
    asyncio.run(setup_bot())
    app.run(host="0.0.0.0", port=PORT, debug=False)
