import logging
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, InlineQueryHandler, MessageHandler, filters

TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
user_alerts = {}  # key: user_id, value: list of alerts (token, target_price)

logging.basicConfig(level=logging.INFO)

# Get current price and 24h change
def get_crypto_data(symbol):
    url = f'https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd&include_24hr_change=true'
    response = requests.get(url).json()
    if symbol in response:
        data = response[symbol]
        return data['usd'], data.get('usd_24h_change', 0)
    return None, None

# Convert symbol (like btc) to full id (like bitcoin)
def get_full_id(symbol):
    mapping = {
        'btc': 'bitcoin',
        'eth': 'ethereum',
        'bnb': 'binancecoin',
        'sol': 'solana'
    }
    return mapping.get(symbol.lower())

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selamat datang! Kirim /price <token> untuk mengetahui harga crypto.\nContoh: /price btc")

# Price command
async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("Kirim /price <symbol> (misalnya: /price btc)")
        return

    symbol = context.args[0].lower()
    coin_id = get_full_id(symbol)
    if not coin_id:
        await update.message.reply_text("Token tidak dikenal.")
        return

    price, change = get_crypto_data(coin_id)
    if price is None:
        await update.message.reply_text("Gagal mengambil data.")
        return

    keyboard = [
        [InlineKeyboardButton("Set Notifikasi", callback_data=f"alert_{symbol}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"💰 Harga {symbol.upper()}: ${price:.2f}\n📉 Perubahan 24 jam: {change:.2f}%",
        reply_markup=reply_markup
    )

# Callback tombol
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("alert_"):
        symbol = data.split("_")[1]
        context.user_data['awaiting_alert'] = symbol
        await query.edit_message_text(f"Masukkan harga USD untuk notifikasi {symbol.upper()}:")

# Tangkap pesan angka untuk notifikasi
async def alert_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'awaiting_alert' not in context.user_data:
        return

    try:
        price_target = float(update.message.text)
        symbol = context.user_data.pop('awaiting_alert')
        user_id = update.effective_user.id
        user_alerts.setdefault(user_id, []).append((symbol, price_target))
        await update.message.reply_text(f"🔔 Notifikasi disetel untuk {symbol.upper()} di harga ${price_target:.2f}")
    except ValueError:
        await update.message.reply_text("Masukkan angka yang valid.")

# Inline query
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.lower()
    results = []

    for symbol in ['btc', 'eth', 'bnb', 'sol']:
        coin_id = get_full_id(symbol)
        price, change = get_crypto_data(coin_id)
        if price is None:
            continue

        results.append(
            InlineQueryResultArticle(
                id=symbol,
                title=f"{symbol.upper()} - ${price:.2f}",
                input_message_content=InputTextMessageContent(
                    f"💰 {symbol.upper()}: ${price:.2f} ({change:+.2f}%)"
                )
            )
        )

    await update.inline_query.answer(results[:10])

# Cek notifikasi berkala
async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    for user_id, alerts in user_alerts.items():
        for symbol, target_price in alerts:
            coin_id = get_full_id(symbol)
            current_price, _ = get_crypto_data(coin_id)
            if current_price is None:
                continue

            if (current_price >= target_price):
                try:
                    await context.bot.send_message(user_id, f"🚨 {symbol.upper()} telah mencapai ${current_price:.2f} (target: ${target_price:.2f})")
                    alerts.remove((symbol, target_price))
                except Exception as e:
                    logging.warning(f"Gagal kirim ke {user_id}: {e}")

# Main function
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, alert_price_input))
    app.job_queue.run_repeating(check_alerts, interval=60, first=10)

    app.run_polling()

if __name__ == '__main__':
    main()
