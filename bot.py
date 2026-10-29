import os
import logging
import asyncio
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask, request, jsonify

# Configuração de logs
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Token e Configurações
TOKEN = "9156028501:AAGO9cUk8dCTdfdYGCkREdv0mYRn8ZQ_koU"
PORT = int(os.environ.get("PORT", "10000"))
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL") # URL automática fornecida pelo Render

# ID numérico do seu Canal VIP e Canal de Divulgação (GT)
CANAL_VIP_ID = "-1004366728974"
CANAL_GT = "-1004377593053"

# Dicionário temporário em memória para armazenar {telegram_id: data_de_expiracao}
REGISTRO_ASSINANTES = {}

# Inicializa o Flask e a Aplicação do Telegram
app = Flask(__name__)
telegram_app = None
loop = None

# 1. Comando /start no Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    keyboard = [
        [InlineKeyboardButton("⭐ Conhecer o Filmex", callback_data="plano_vip")],
        [InlineKeyboardButton("💬 Falar com o Suporte", url="https://t.me/-1004377593053")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Olá, {user_name} 🍿.\n\n"
        "Participe do nosso grupo para ter acesso liberado ao canal de filmes e séries!",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# 2. Cliques nos botões do Telegram (Com captura dinâmica do ID via parâmetro ref)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "plano_vip":
        # Captura automaticamente o ID do Telegram do cliente que clicou no botão
        telegram_id_cliente = update.effective_user.id
        
        # Injeta o ID do cliente na URL da Kiwify via parâmetro ref de forma invisível
        link_kiwify = f"https://pay.kiwify.com.br/cGoSyA8?ref={telegram_id_cliente}"
        
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
            [InlineKeyboardButton("💬 Falar com o Suporte", url="https://t.me/-1004377593053")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Escolha uma opção:", reply_markup=reply_markup)

# 3. Rota principal do Flask que recebe as mensagens do Telegram via Webhook
@app.route(f'/{TOKEN}', methods=['POST'])
def telegram_webhook():
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, telegram_app.bot)
    
    # Processa o update de forma segura usando o loop principal
    future = asyncio.run_coroutine_threadsafe(telegram_app.process_update(update), loop)
    future.result()
    
    return jsonify({"status": "ok"}), 200

# 4. Rota de Ping (Anti-Sleep para o UptimeRobot)
@app.route('/ping', methods=['GET'])
def ping_server():
    return "Pong! Servidor ativo.", 200

# 5. Rota de Webhook da Kiwify (Entrega Automatizada do Link VIP e Gestão de Prazos)
@app.route('/webhook-kiwify', methods=['POST'])
def webhook_kiwify():
    dados = request.json
    try:
        status = dados.get("status") or dados.get("order_status")
        
        # Verifica se o pagamento foi aprovado
        if status == "paid" or status == "approved":
            cliente_telegram_id = dados.get("ref") or dados.get("tracking", {}).get("ref") or dados.get("custom_field")
            
            if cliente_telegram_id:
                cliente_telegram_id = int(cliente_telegram_id)
                
                # Define a validade do acesso (Exemplo: 30 dias para mensalidade)
                expire_access_date = datetime.datetime.now() + datetime.timedelta(days=30)
                
                # Salva ou atualiza a data limite do assinante no registro
                REGISTRO_ASSINANTES[cliente_telegram_id] = expire_access_date
                
                async def enviar_convite_e_acesso():
                    # Link de convite válido pelo período correspondente
                    link_convite = await telegram_app.bot.create_chat_invite_link(
                        chat_id=CANAL_VIP_ID,
                        member_limit=1,
                        expire_date=expire_access_date
                    )
                    
                    await telegram_app.bot.send_message(
                        chat_id=cliente_telegram_id,
                        text=f"🎉 **Pagamento Aprovado com Sucesso!**\n\n"
                             f"Obrigado por assinar o **Filmex**!\n"
                             f"Aqui está o seu link de acesso exclusivo para o canal VIP:\n\n"
                             f"{link_convite.invite_link}\n\n"
                             f"⚠️ *Este link é de uso único e sua assinatura é válida por 30 dias.*"
                    )

                future = asyncio.run_coroutine_threadsafe(enviar_convite_e_acesso(), loop)
                future.result()

        return jsonify({"status": "recebido"}), 200
    except Exception as e:
        logging.error(f"Erro no webhook Kiwify: {e}")
        return jsonify({"status": "erro"}), 500

# 6. Tarefa em background para verificar e remover assinantes vencidos
async def verificar_assinaturas_vencidas():
    await asyncio.sleep(20) # Aguarda o bot iniciar
    while True:
        try:
            agora = datetime.datetime.now()
            vencidos = [user_id for user_id, data_exp in REGISTRO_ASSINANTES.items() if agora > data_exp]
            
            for user_id in vencidos:
                try:
                    # Remove o usuário do canal VIP (bane e desbane em seguida para revogar o acesso)
                    await telegram_app.bot.ban_chat_member(chat_id=CANAL_VIP_ID, user_id=user_id)
                    await telegram_app.bot.unban_chat_member(chat_id=CANAL_VIP_ID, user_id=user_id)
                    
                    # Avisa o usuário no chat privado que o acesso expirou
                    await telegram_app.bot.send_message(
                        chat_id=user_id,
                        text="⚠️ **Sua assinatura do Filmex expirou!**\n\n"
                             f"O seu acesso ao canal VIP foi encerrado. Para continuar desfrutando de todo o conteúdo, "
                             f"renove a sua assinatura através do nosso bot com o comando /start."
                    )
                    
                    logging.info(f"Usuário {user_id} removido do canal por expiração de prazo.")
                except Exception as inner_err:
                    logging.error(f"Não foi possível remover o usuário {user_id}: {inner_err}")
                
                del REGISTRO_ASSINANTES[user_id]
                
        except Exception as e:
            logging.error(f"Erro na verificação de assinaturas vencidas: {e}")
        
        await asyncio.sleep(3600)

# 7. Tarefa em loop para envio automático do texto persuasivo para o canal (Com redirecionamento direto para o chat do bot)
async def loop_envio_canal():
    await asyncio.sleep(10)
    
    while True:
        try:
            texto_automatico = (
                "🍿 **Já imaginou ter acesso aos melhores lançamentos sem precisar procurar em dezenas de sites?**\n\n"
                "No **Filmex**, nós filtramos e organizamos o melhor do cinema e das séries para você assistir direto no Telegram, "
                "sem anúncios chatos, sem links maliciosos e com alta qualidade.\n\n"
                "🎬 **O que você encontra por hierarquia:**\n"
                "• Conteúdos atualizados constantemente.\n"
                "• Um ambiente fechado, organizado e sem distrações.\n"
                "• Tudo na palma da sua mão, pronto para dar o play.\n\n"
                "Quer fazer parte do nosso canal VIP e liberar o seu acesso completo hoje mesmo?"
            )
            
            # Botão apontando diretamente para o chat do bot no Telegram
            keyboard = [[InlineKeyboardButton("⭐ Conhecer o Filmex", url="https://t.me/QThin_bot")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await telegram_app.bot.send_message(
                chat_id=CANAL_GT,
                text=texto_automatico,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            
            logging.info("Mensagem automática enviada com sucesso para o canal GT.")
        except Exception as e:
            logging.error(f"Erro ao enviar mensagem automática no loop: {e}")
        
        await asyncio.sleep(7200) # A cada 2 horas

@app.route('/')
def home():
    return "Filmex rodando!"

async def setup_bot():
    global telegram_app, loop
    loop = asyncio.get_running_loop()
    
    telegram_app = Application.builder().token(TOKEN).build()

    telegram_app.add_handler(CommandHandler('start', start))
    telegram_app.add_handler(CallbackQueryHandler(button_handler))

    await telegram_app.initialize()
    
    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/{TOKEN}"
        await telegram_app.bot.set_webhook(url=webhook_url)
        logging.info(f"Webhook configurado com sucesso para: {webhook_url}")

    await telegram_app.start()
    
    asyncio.create_task(loop_envio_canal())
    asyncio.create_task(verificar_assinaturas_vencidas())
    
    await asyncio.Event().wait()

if __name__ == '__main__':
    from threading import Thread
    
    def run_flask():
        app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    try:
        asyncio.run(setup_bot())
    except KeyboardInterrupt:
        pass
