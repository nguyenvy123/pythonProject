from telegram import Bot, Update, BotCommand
from telegram.error import TelegramError
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz
import logging
import json

from telegram.ext import Updater, CommandHandler, CallbackContext

# --- Cấu hình ---
BOT_TOKEN = '7696186849:AAHUow8NJaYAkR1Zyminds-Sh5juF0MLY2U'
GROUP_CHAT_ID = -4040600344  # Thay bằng ID group của bạn

# --- Khởi tạo bot và scheduler ---
bot = Bot(token=BOT_TOKEN)
scheduler = BlockingScheduler()
updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# --- Biến để lưu message_id của poll ---
message_id = None

# --- Đọc danh sách users từ file ---
def load_members():
    try:
        with open('members.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []  # Nếu file không tồn tại, trả về danh sách rỗng

# --- Lưu danh sách users vào file ---
def save_members():
    with open('members.json', 'w', encoding='utf-8') as f:
        json.dump(members_to_tag, f, ensure_ascii=False, indent=4)

# Danh sách các ngày trong tuần bằng tiếng Việt
days_of_week = {
    0: 'Thứ Hai',
    1: 'Thứ Ba',
    2: 'Thứ Tư',
    3: 'Thứ Năm',
    4: 'Thứ Sáu',
    5: 'Thứ Bảy',
    6: 'Chủ Nhật'
}

# --- Danh sách members để tag ---
members_to_tag = load_members()

# --- Hàm gửi poll ---
def send_poll(context: CallbackContext = None):
    global message_id
    try:
        # Lấy ngày hiện tại
        today = datetime.now()
        day_of_week = today.weekday()  # Số thứ trong tuần (0-6)
        today_date = today.strftime("%d/%m/%Y")  # Format ngày tháng năm

        # Lấy tên ngày từ danh sách
        week_day_name = days_of_week[day_of_week]

        # Tạo câu hỏi với ngày
        question = f"Điểm danh hôm nay {week_day_name}, {today_date} nhé?"
        # Gửi poll
        message = bot.send_poll(
            chat_id=GROUP_CHAT_ID,
            question=question,
            options=["✅ Có", "❌ Không"],
            is_anonymous=False,
            allows_multiple_answers=False
        )
        message_id = message.message_id  # Lưu message_id để đóng poll sau
        # Pin message sau khi gửi poll
        bot.pin_chat_message(chat_id=GROUP_CHAT_ID, message_id=message_id, disable_notification=True)
        print(f"Đã gửi poll và pin message_id: {message_id}")

        # Gửi tag all thành viên
        if members_to_tag:
            batch_size = 5
            for i in range(0, len(members_to_tag), batch_size):
                batch = members_to_tag[i:i + batch_size]
                tag_message = " ".join(batch)
                bot.send_message(chat_id=GROUP_CHAT_ID, text=tag_message)

    except TelegramError as e:
        print(f"Lỗi khi gửi poll: {e}")

# --- Hàm đóng poll ---
def close_poll():
    global message_id
    try:
        if message_id:
            bot.stop_poll(chat_id=GROUP_CHAT_ID, message_id=message_id)
            print("Đã đóng poll.")
        else:
            print("Không tìm thấy message_id để đóng poll.")
    except TelegramError as e:
        print(f"Lỗi khi đóng poll: {e}")

# --- Handler cho lệnh /start ---
def start_command(update: Update, context: CallbackContext):
    if update.effective_chat.id == GROUP_CHAT_ID:
        send_poll()
    else:
        print(f"Không đúng group, bỏ qua chat id: {update.effective_chat.id}")


# --- Handler cho lệnh /add ---
def add_users(update: Update, context: CallbackContext):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return

    new_users = context.args  # Lấy danh sách các tham số sau /add
    added_users = []

    for user in new_users:
        if user.startswith("@") and user not in members_to_tag:
            members_to_tag.append(user)
            added_users.append(user)

    if added_users:
        save_members()  # Lưu lại danh sách vào file
        update.message.reply_text(f"Đã thêm: {' '.join(added_users)}")
    else:
        update.message.reply_text("Không có user mới hợp lệ để thêm.")

# --- Handler cho lệnh /help ---
def help_command(update: Update, context: CallbackContext):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return

    help_text = (
        "📋 *Danh sách lệnh của bot:*\n"
        "/start - Gửi poll điểm danh ngay lập tức.\n"
        "/add @username1 @username2 - Thêm các username vào danh sách tag khi gửi poll.\n"
        "/help - Hiển thị hướng dẫn này.\n"
    )
    update.message.reply_text(help_text, parse_mode='Markdown')

def set_bot_commands():
    commands = [
        BotCommand("start", "Gửi poll điểm danh ngay lập tức"),
        BotCommand("add", "Thêm username vào danh sách tag"),
        BotCommand("help", "Hiển thị hướng dẫn sử dụng bot")
    ]
    try:
        bot.set_my_commands(commands)
        print("Đã thiết lập danh sách lệnh cho bot.")
    except TelegramError as e:
        print(f"Lỗi khi thiết lập danh sách lệnh: {e}")
# --- Gán handler ---
dispatcher.add_handler(CommandHandler('start', start_command))
dispatcher.add_handler(CommandHandler('add', add_users))
dispatcher.add_handler(CommandHandler('help', help_command))
# --- Lên lịch ---
timezone = pytz.timezone('Asia/Ho_Chi_Minh')

scheduler.add_job(
    send_poll,
    CronTrigger(hour=9, minute=00, day_of_week='mon,wed,fri', timezone=timezone)
)

scheduler.add_job(
    close_poll,
    CronTrigger(hour=17, minute=30, day_of_week='mon,wed,fri', timezone=timezone)
)

# --- Log ---
logging.basicConfig()
# --- Bắt đầu bot ---
set_bot_commands()
updater.start_polling()
# scheduler.start()
updater.idle()
