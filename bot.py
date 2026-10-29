import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from flask import Flask, request, jsonify

# Configuração de logs
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Token inserido diretamente para evitar falhas de leitura no Render
TOKEN = "9156028501:AAGO9cUk8dCTdfdYGCkREdv0mYRn8ZQ_koU"
PORT = int(os.environ.get("PORT", "10000"))

# Inicializa o Flask e a aplicação do Telegram
app = Flask(__name__)
telegram_app = None

# 1. Comando /start no Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    keyboard = [
        [InlineKeyboardButton("⭐ Conhecer o Filmex", callback_data="plano_vip")],
        [InlineKeyboardButton("💬 Falar com o Suporte", url="https://t.me/@Filmex_Grupo")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f" 🍿.\n\n"
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

    elif query.data == "voltar_inicio":
        keyboard = [
            [InlineKeyboardButton("⭐ Conhecer grupo Filmex", callback_data="plano_vip")],
            [InlineKeyboardButton("💬 Falar com o Suporte", url="https://t.me/")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Escolha uma opção:", reply_markup=reply_markup)

# 3. Rota de Ping (Anti-Sleep para o UptimeRobot)
@app.route('/ping', methods=['GET'])
def ping_server():
    return "Pong! Servidor ativo.", 200

CANAL_VIP_ID = "-1001234567890"  # Substitua pelo ID real do seu canal/grupo

# 5. Rota de Pagamento da Kiwify com automação de envio do link
@app.route('/webhook-kiwify', methods=['POST'])
def webhook_kiwify():
    dados = request.json
    try:
        status = dados.get("status") or dados.get("order_status")
        
        # Verifica se a compra foi aprovada/paga
        if status == "paid" or status == "approved":
            # Tenta capturar o Telegram ID ou o e-mail do cliente enviado pela Kiwify
            # (Nota: O ideal é configurar parâmetros UTM ou o ID do Telegram no checkout da Kiwify)
            cliente_telegram_id = dados.get("customer", {}).get("telegram_id") # ou campo personalizado
            
            # Como alternativa segura caso use o e-mail para notificar o suporte ou salvar no banco:
            # cliente_email = dados.get("customer", {}).get("email")

            if cliente_telegram_id:
                # Cria um link de convite que expira em 24 horas e serve para apenas 1 uso
                import datetime
                expire_date = datetime.datetime.now() + datetime.timedelta(days=1)
                
                # Executa a criação do link via API do Telegram de forma assíncrona
                async def enviar_convite():
                    link_convite = await telegram_app.bot.create_chat_invite_link(
                        chat_id=CANAL_VIP_ID,
                        member_limit=1,
                        expire_date=expire_date
                    )
                    # Envia o link diretamente para o chat privado do cliente no Telegram
                    await telegram_app.bot.send_message(
                        chat_id=cliente_telegram_id,
                        text=f"🎉 **Pagamento Aprovado com Sucesso!**\n\n"
                             f"Obrigado por assinar o **Filmex**!\n"
                             f"Aqui está o seu link de acesso exclusivo e individual para o nosso canal VIP:\n\n"
                             f"{link_convite.invite_link}\n\n"
                             f"⚠️ *Este link é de uso único e expira em 24 horas.*"
                    )

                asyncio.run(enviar_convite())

        return jsonify({"status": "recebido"}), 200
    except Exception as e:
        logging.error(f"Erro no webhook Kiwify: {e}")
        return jsonify({"status": "erro"}), 500

@app.route('/')
def home():
    return "Filmex!"

async def main():
    global telegram_app
    telegram_app = ApplicationBuilder().token(TOKEN).build()

    telegram_app.add_handler(CommandHandler('start', start))
    telegram_app.add_handler(CallbackQueryHandler(button_handler))

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling()
    
    # Roda o servidor Flask em segundo plano na porta exigida pelo Render
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

if __name__ == '__main__':
    asyncio.run(main())
