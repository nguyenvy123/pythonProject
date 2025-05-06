from telegram import Bot, Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz
import logging
import json

from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler

# --- Cấu hình logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Cấu hình ---
BOT_TOKEN = '7696186849:AAHUow8NJaYAkR1Zyminds-Sh5juF0MLY2U'
GROUP_CHAT_ID = -1002548146910  # Thay bằng ID group của bạn

# --- Khởi tạo bot và scheduler ---
bot = Bot(token=BOT_TOKEN)
scheduler = BlockingScheduler()
updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# --- Biến để lưu message_id của poll ---
message_id = None
# --- Biến để lưu các yêu cầu xác nhận thanh toán ---
pending_confirmations = {}  # {message_id: username}
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

# --- Đọc danh sách user nợ từ file debts.json ---
def load_debts():
    try:
        with open('debts.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('debts', [])
    except FileNotFoundError:
        return []  # Nếu file không tồn tại, trả về danh sách rỗng

# --- Lưu danh sách user nợ vào file debts.json ---
def save_debts(debts):
    with open('debts.json', 'w', encoding='utf-8') as f:
        json.dump({'debts': debts}, f, ensure_ascii=False, indent=4)

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
debts = load_debts()
# --- Hàm xử lý tất cả cập nhật để debug ---
def debug_update(update: Update, context: CallbackContext):
    logger.info(f"Nhận cập nhật: {update}")
    print(f"Nhận cập nhật: {update}")

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

# --- Handler cho lệnh /vl ---
def vl_command(update: Update, context: CallbackContext):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return

    args = context.args
    if not args or not all(arg.startswith("@") for arg in args):
        update.message.reply_text("Vui lòng cung cấp ít nhất một username hợp lệ: /vl @username1 @username2 ...")
        return

    try:
        added_users = []
        already_debted = []
        for username in args:
            if username not in debts:
                debts.append(username)
                added_users.append(username)
            else:
                already_debted.append(username)

        if added_users:
            save_debts(debts)
            logger.info(f"Đã ghi nợ cho {added_users} (via /vl), debts: {debts}")
            print(f"Đã ghi nợ cho {added_users} (via /vl), debts: {debts}")

        response = ""
        if added_users:
            response += f"Đã ghi nợ cho {' '.join(added_users)}."
        if already_debted:
            response += f" Các user đã có trong danh sách nợ: {' '.join(already_debted)}."
        if not added_users and already_debted:
            response = f"Tất cả user đã có trong danh sách nợ: {' '.join(already_debted)}."

        update.message.reply_text(response.strip())

    except Exception as e:
        logger.error(f"Lỗi khi ghi nợ cho {args} (/vl): {e}")
        print(f"Lỗi khi ghi nợ cho {args} (/vl): {e}")
        update.message.reply_text("Đã xảy ra lỗi khi ghi nợ.")

# --- Handler cho lệnh /paid ---
def paid_command(update: Update, context: CallbackContext):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return

    args = context.args
    if not args or len(args) != 1 or not args[0].startswith("@"):
        update.message.reply_text("Vui lòng cung cấp đúng định dạng: /paid @username")
        return

    username = args[0]
    try:
        # Tạo inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("Đã thanh toán", callback_data="paid_yes"),
                InlineKeyboardButton("Chưa thanh toán", callback_data="paid_no")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Gửi tin nhắn xác nhận trong nhóm
        message = bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=f"Yêu cầu xác nhận thanh toán cố định cho {username}.",
            reply_markup=reply_markup
        )
        pending_confirmations[message.message_id] = username  # Lưu message_id và username
        logger.info(f"Đã gửi yêu cầu xác nhận cho {username}, message_id: {message.message_id}, pending_confirmations: {pending_confirmations}")
        print(f"Đã gửi yêu cầu xác nhận cho {username}, message_id: {message.message_id}, pending_confirmations: {pending_confirmations}")


    except TelegramError as e:
        logger.error(f"Lỗi khi gửi yêu cầu xác nhận: {e}")
        print(f"Lỗi khi gửi yêu cầu xác nhận: {e}")
        update.message.reply_text("Đã xảy ra lỗi khi gửi yêu cầu xác nhận.")

def paidvl_command(update: Update, context: CallbackContext):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return

    args = context.args
    if not args or len(args) != 1 or not args[0].startswith("@"):
        update.message.reply_text("Vui lòng cung cấp đúng định dạng: /paidvl @username")
        return

    username = args[0]
    try:
        keyboard = [
            [
                InlineKeyboardButton("Đã thanh toán", callback_data="paid_yes"),
                InlineKeyboardButton("Chưa thanh toán", callback_data="paid_no")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=f"Yêu cầu xác nhận thanh toán vãng lai cho {username}.",
            reply_markup=reply_markup
        )
        pending_confirmations[message.message_id] = username
        logger.info(f"Đã gửi yêu cầu xác nhận cho {username} (via /paidvl), message_id: {message.message_id}, pending_confirmations: {pending_confirmations}")
        print(f"Đã gửi yêu cầu xác nhận cho {username} (via /paidvl), message_id: {message.message_id}, pending_confirmations: {pending_confirmations}")

    except TelegramError as e:
        logger.error(f"Lỗi khi gửi yêu cầu xác nhận (/paidvl): {e}")
        print(f"Lỗi khi gửi yêu cầu xác nhận (/paidvl): {e}")
        update.message.reply_text("Đã xảy ra lỗi khi gửi yêu cầu xác nhận.")

# --- Handler cho lệnh /list_debts ---
def list_debts_command(update: Update, context: CallbackContext):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return

    try:
        if debts:
            debts_list = ", ".join(debts)
            update.message.reply_text(f"Danh sách user đang nợ: {debts_list}")
        else:
            update.message.reply_text("Hiện không có user nào đang nợ.")
        logger.info(f"Đã hiển thị danh sách nợ: {debts}")
        print(f"Đã hiển thị danh sách nợ: {debts}")
    except Exception as e:
        logger.error(f"Lỗi khi hiển thị danh sách nợ: {e}")
        print(f"Lỗi khi hiển thị danh sách nợ: {e}")
        update.message.reply_text("Đã xảy ra lỗi khi hiển thị danh sách nợ.")

# --- Handler cho callback query từ inline keyboard ---
def handle_callback_query(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    logger.info(f"Nhận callback: data={query.data}, from_user={query.from_user.id}, message_id={query.message.message_id}")
    print(f"Nhận callback: data={query.data}, from_user={query.from_user.id}, message_id={query.message.message_id}")

    data = query.data
    if data in ["paid_yes", "paid_no"]:
        try:
            admins = bot.get_chat_administrators(GROUP_CHAT_ID)
            admin_ids = [admin.user.id for admin in admins]
            logger.info(f"Danh sách admin_ids: {admin_ids}")
            print(f"Danh sách admin_ids: {admin_ids}")
            if query.from_user.id not in admin_ids:
                bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text="Chỉ admin mới có thể xác nhận trạng thái thanh toán."
                )
                logger.warning(f"Người không phải admin ({query.from_user.id}) cố gắng xác nhận")
                print(f"Người không phải admin ({query.from_user.id}) cố gắng xác nhận")
                return

            message_id = query.message.message_id
            username = pending_confirmations.get(message_id)
            logger.info(f"Tra cứu pending_confirmations, message_id={message_id}, username={username}")
            print(f"Tra cứu pending_confirmations, message_id={message_id}, username={username}")
            if not username:
                bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text="Yêu cầu xác nhận không còn hợp lệ."
                )
                logger.warning(f"Không tìm thấy username cho message_id={message_id}")
                print(f"Không tìm thấy username cho message_id={message_id}")
                return

            is_paid = data == "paid_yes"
            status_text = "đã thanh toán" if is_paid else "chưa thanh toán"
            bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=f"Admin đã xác nhận {username} {status_text}."
            )
            logger.info(f"Đã xác nhận {username} {status_text}")
            print(f"Đã xác nhận {username} {status_text}")

            # Nếu là /paidvl và xác nhận "Đã thanh toán", xóa nợ
            if message_id in pending_confirmations and is_paid:
                if username in debts:
                    debts.remove(username)
                    save_debts(debts)
                    logger.info(f"Đã xóa nợ cho {username}, debts hiện tại: {debts}")
                    print(f"Đã xóa nợ cho {username}, debts hiện tại: {debts}")

            # Ẩn inline keyboard
            bot.edit_message_reply_markup(
                chat_id=GROUP_CHAT_ID,
                message_id=message_id,
                reply_markup=None
            )
            logger.info(f"Đã ẩn inline keyboard cho message_id={message_id}")
            print(f"Đã ẩn inline keyboard cho message_id={message_id}")

            # Xóa yêu cầu khỏi pending_confirmations
            del pending_confirmations[message_id]
            logger.info(f"Đã xóa pending_confirmations cho message_id={message_id}, pending_confirmations hiện tại: {pending_confirmations}")
            print(f"Đã xóa pending_confirmations cho message_id={message_id}, pending_confirmations hiện tại: {pending_confirmations}")

        except TelegramError as e:
            logger.error(f"Lỗi trong handle_callback_query: {e}")
            print(f"Lỗi trong handle_callback_query: {e}")
            bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text="Đã xảy ra lỗi khi xử lý xác nhận."
            )
# --- Handler cho lệnh /help ---
def help_command(update: Update, context: CallbackContext):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return

    help_text = (
        "📋 *Danh sách lệnh của bot:*\n"
        "/start - Gửi poll điểm danh ngay lập tức.\n"
        "/add @username1 @username2 - Thêm các username vào danh sách tag khi gửi poll.\n"
        # "/paidcd @username - Yêu cầu admin xác nhận trạng thái thanh toán cố định.\n"
        "/vl @username - Ghi nợ cho user.\n"
        "/paidvl @username - Yêu cầu admin xác nhận trạng thái thanh toán vãng lai\n"
        "/list_no - Hiển thị danh sách user đang nợ.\n"
        "/help - Hiển thị hướng dẫn này.\n"
    )
    update.message.reply_text(help_text, parse_mode='Markdown')

def set_bot_commands():
    commands = [
        BotCommand("start", "Gửi poll điểm danh ngay lập tức"),
        BotCommand("add", "Thêm username vào danh sách tag"),
        BotCommand("vl", "Ghi nợ cho user"),
        # BotCommand("paidcd", "Yêu cầu xác nhận trạng thái thanh toán"),
        BotCommand("paidvl", "Yêu cầu xác nhận trạng thái thanh toán vl"),
        BotCommand("list_no", "Hiển thị danh sách user đang nợ"),
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
dispatcher.add_handler(CommandHandler('vl', vl_command))
dispatcher.add_handler(CommandHandler('paidvl', paidvl_command))
# dispatcher.add_handler(CommandHandler('paidcd', paid_command))
dispatcher.add_handler(CommandHandler('list_no', list_debts_command))
dispatcher.add_handler(CommandHandler('help', help_command))
dispatcher.add_handler(CallbackQueryHandler(handle_callback_query))
logger.info("Đã đăng ký tất cả handlers, bao gồm CallbackQueryHandler")
print("Đã đăng ký tất cả handlers, bao gồm CallbackQueryHandler")

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
# --- Kiểm tra và xóa webhook để đảm bảo polling ---
try:
    webhook_info = bot.get_webhook_info()
    if webhook_info.url:
        bot.delete_webhook()
        logger.info("Đã xóa webhook để sử dụng polling")
        print("Đã xóa webhook để sử dụng polling")
    else:
        logger.info("Không có webhook, sử dụng polling")
        print("Không có webhook, sử dụng polling")
except TelegramError as e:
    logger.error(f"Lỗi khi kiểm tra webhook: {e}")
    print(f"Lỗi khi kiểm tra webhook: {e}")
# --- Log ---
logging.basicConfig()
# --- Bắt đầu bot ---
set_bot_commands()
logger.info("Bắt đầu polling...")
print("Bắt đầu polling...")
updater.start_polling()
# scheduler.start()
updater.idle()
