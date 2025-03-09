import json
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackContext,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
import os
from dotenv import load_dotenv

load_dotenv()

# Конфигурация
ADMINS = [6097752198, 5173037460]  # Замените на ID администраторов
with open('Fruits.json', 'r', encoding='utf-8') as f:
    FRUITS_DATA = json.load(f)
USER_DATA_FILE = "users_data.json"

# Вспомогательные функции
def load_user_data():
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"users": {}}

def save_user_data(data):
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

def generate_fruit(rarity=None):
    if not rarity:
        rarity_weights = {"Common": 40, "Uncommon": 30, "Rare": 20, "Legendary": 8, "Mythical": 2}
        rarity = random.choices(list(rarity_weights.keys()), weights=list(rarity_weights.values()))[0]
    return random.choice(FRUITS_DATA["devil_fruits"][rarity])

# Обработчики сообщений
async def start(update: Update, context: CallbackContext):
    help_text = (
        "🍇 Бот для коллекционирования фруктов!\n"
        "Пиши:\n"
        "• «Получить фрукт» - раз в 4 часа\n"
        "• «Мои фрукты» - показать коллекцию"
    )
    await update.message.reply_text(help_text)

async def handle_text_messages(update: Update, context: CallbackContext):
    user = update.effective_user
    text = update.message.text.strip().lower()
    
    # Админ-команды
    if is_admin(user.id):
        if text.startswith("отобрать карту "):
            parts = text.split(" ", 3)
            if len(parts) < 4:
                await update.message.reply_text("❌ Формат: Отобрать карту @username Название_Карты")
                return
            target_username = parts[2].replace("@", "")
            fruit_name = parts[3]
            await revoke_fruit(update, context, target_username, fruit_name)
            return
        
        if text == "все карты":
            await send_all_fruits(update)
            return
        
        if text.startswith("получить фрукт "):
            fruit_name = text[14:].strip()
            await give_specific_fruit(update, context, fruit_name)
            return
    
    # Обычные команды
    if text == "получить фрукт":
        await get_fruit(update, context)
    elif text == "мои фрукты":
        await my_fruits(update, context)

# Основная логика
async def get_fruit(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = str(user.id)
    data = load_user_data()
    
    user_data = data["users"].setdefault(user_id, {
        "last_spin": None, 
        "inventory": [], 
        "username": user.username or user.full_name
    })
    
    if user_data["last_spin"]:
        last_spin = datetime.fromisoformat(user_data["last_spin"])
        if (datetime.now() - last_spin) < timedelta(hours=4):
            time_left = last_spin + timedelta(hours=4) - datetime.now()
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            await update.message.reply_text(f"⏳ Следующая попытка через {hours} ч. {minutes} мин.")
            return
    
    new_fruit = generate_fruit()
    duplicates = [item for item in user_data["inventory"] if item["name"] == new_fruit["name"]]
    
    user_data["inventory"].append({**new_fruit, "obtained": datetime.now().isoformat()})
    user_data["last_spin"] = datetime.now().isoformat()
    save_user_data(data)
    
    msg = (
        f"🎉 {user.mention_html()} получил(а):\n"
        f"<b>{new_fruit['name']}</b>\n"
        f"🏷 Редкость: {new_fruit['rarity']}\n"
        f"⚔ Урон: {new_fruit['damage']}\n"
        f"❤ Здоровье: {new_fruit.get('health', 'N/A')}"
    )
    if duplicates:
        msg += f"\n⚠ Дубликатов: {len(duplicates)+1}"
    
    await update.message.reply_text(msg, parse_mode="HTML")

async def give_specific_fruit(update: Update, context: CallbackContext, fruit_name: str):
    user = update.effective_user
    target_fruit = None
    
    for rarity in FRUITS_DATA["devil_fruits"]:
        for fruit in FRUITS_DATA["devil_fruits"][rarity]:
            if fruit["name"].lower() == fruit_name.lower():
                target_fruit = fruit
                break
        if target_fruit:
            break
    
    if not target_fruit:
        await update.message.reply_text("❌ Фрукт не найден!")
        return
    
    data = load_user_data()
    user_data = data["users"].setdefault(str(user.id), {"last_spin": None, "inventory": []})
    
    duplicates = [item for item in user_data["inventory"] if item["name"] == target_fruit["name"]]
    user_data["inventory"].append(target_fruit.copy())
    save_user_data(data)
    
    msg = (
        f"🎉 Админ {user.mention_html()} получил:\n"
        f"<b>{target_fruit['name']}</b>\n"
        f"🏷 Редкость: {target_fruit['rarity']}\n"
        f"⚔ Урон: {target_fruit['damage']}"
    )
    if duplicates:
        msg += f"\n⚠ Дубликатов: {len(duplicates)+1}"
    
    await update.message.reply_text(msg, parse_mode="HTML")

async def revoke_fruit(update: Update, context: CallbackContext, target_username: str, fruit_name: str):
    data = load_user_data()
    target_user_id = None
    
    for user_id, user_data in data["users"].items():
        if user_data.get("username", "").lower() == target_username.lower():
            target_user_id = user_id
            break
    
    if not target_user_id:
        await update.message.reply_text("❌ Пользователь не найден!")
        return
    
    new_inventory = []
    removed = False
    for item in data["users"][target_user_id]["inventory"]:
        if item["name"].lower() == fruit_name.lower():
            removed = True
        else:
            new_inventory.append(item)
    
    if not removed:
        await update.message.reply_text("❌ У пользователя нет такой карты!")
        return
    
    data["users"][target_user_id]["inventory"] = new_inventory
    save_user_data(data)
    await update.message.reply_text(f"✅ Карта {fruit_name} отобрана у @{target_username}")

async def send_all_fruits(update: Update):
    fruits_list = ["📜 Все доступные карты:\n"]
    
    for rarity in ["Common", "Uncommon", "Rare", "Legendary", "Mythical"]:
        fruits_list.append(f"\n🔮 {rarity} 🔮")
        for fruit in FRUITS_DATA["devil_fruits"][rarity]:
            fruits_list.append(f"- {fruit['name']} ({fruit['type']})")
    
    try:
        await update.get_bot().send_message(
            chat_id=update.effective_user.id,
            text="\n".join(fruits_list)
        )
    except Exception as e:
        await update.message.reply_text("⚠ Напишите мне в личные сообщения для получения списка!")

# Инвентарь
async def my_fruits(update: Update, context: CallbackContext):
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    keyboard = [
        [InlineKeyboardButton(rarity, callback_data=f"rarity_{rarity}_{chat_id}")] 
        for rarity in ["Common", "Uncommon", "Rare", "Legendary", "Mythical"]
    ]
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"{user.first_name}, ваши фрукты:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_rarity_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    rarity, chat_id = data_parts[1], data_parts[2]
    
    user_id = str(query.from_user.id)
    data = load_user_data()
    
    filtered = [item for item in data["users"].get(user_id, {}).get("inventory", []) 
                if item.get("rarity") == rarity]
    
    if not filtered:
        await query.edit_message_text(f"🚫 Нет фруктов с редкостью {rarity}")
        return
    
    context.user_data.update({
        "current_rarity": rarity,
        "current_index": 0,
        "filtered_items": filtered,
        "chat_id": chat_id
    })
    
    await show_card(update, context)

async def show_card(update: Update, context: CallbackContext):
    query = update.callback_query
    if query:
        await query.answer()
    
    user_data = context.user_data
    index = user_data["current_index"]
    items = user_data["filtered_items"]
    item = items[index]
    
    nav_buttons = []
    if index > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data="prev"))
    if index < len(items) - 1:
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data="next"))
    
    message = (
        f"🍇 Фрукт {index + 1}/{len(items)}\n"
        f"📛 <b>{item['name']}</b>\n"
        f"🏷 Редкость: {item['rarity']}\n"
        f"🔮 Тип: {item['type']}\n"
        f"⚔ Урон: {item['damage']}\n"
        f"❤ Здоровье: {item.get('health', 'N/A')}"
    )
    
    if query:
        await query.edit_message_text(text=message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([nav_buttons]))
    else:
        await context.bot.send_message(
            chat_id=user_data["chat_id"],
            text=message,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([nav_buttons])
        )

async def handle_navigation(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    action = query.data
    user_data = context.user_data
    
    if action == "prev":
        user_data["current_index"] -= 1
    elif action == "next":
        user_data["current_index"] += 1
    
    await show_card(update, context)

# Запуск
def main():
    application = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_rarity_choice, pattern="^rarity_"))
    application.add_handler(CallbackQueryHandler(handle_navigation, pattern="^(prev|next)"))
    
    application.run_polling()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    application.run_polling()
    main()
