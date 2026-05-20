"""
기차 취소표 자동 예매 텔레그램 봇
python-telegram-bot 13.x 버전용
"""

import os
import logging
import threading
import time
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Updater, CommandHandler, MessageHandler,
    ConversationHandler, CallbackContext, Filters
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_TOKEN"]
ALLOWED_USER_ID = int(os.environ.get("ALLOWED_USER_ID", "0"))

(RAIL, USERNAME, PASSWORD, DEP, ARR, DATE, TIME_STR, SEAT, PAX, CONFIRM) = range(10)

STATIONS_SRT = ["수서","동탄","평택지제","천안아산","오송","대전","김천구미",
                "동대구","경주","울산","부산","광주송정","목포","여수EXPO"]
STATIONS_KTX = ["서울","용산","광명","수원","천안아산","오송","대전","김천구미",
                "동대구","경주","울산(통도사)","부산","마산","광주송정","목포","강릉"]

running_tasks = {}

def is_allowed(update: Update) -> bool:
    if ALLOWED_USER_ID == 0:
        return True
    return update.effective_user.id == ALLOWED_USER_ID

def start(update: Update, ctx: CallbackContext):
    if not is_allowed(update):
        update.message.reply_text("❌ 권한이 없습니다.")
        return ConversationHandler.END
    kb = [["SRT", "코레일 KTX"]]
    update.message.reply_text(
        "🚄 기차 취소표 자동 예매 봇\n\n어떤 기차를 예매하시겠어요?",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )
    return RAIL

def get_rail(update: Update, ctx: CallbackContext):
    txt = update.message.text.strip()
    if txt not in ["SRT", "코레일 KTX"]:
        update.message.reply_text("SRT 또는 코레일 KTX 중 선택해주세요.")
        return RAIL
    ctx.user_data["rail"] = "SRT" if "SRT" in txt else "KTX"
    update.message.reply_text("아이디(회원번호 또는 이메일)를 입력해주세요:",
                              reply_markup=ReplyKeyboardRemove())
    return USERNAME

def get_username(update: Update, ctx: CallbackContext):
    ctx.user_data["username"] = update.message.text.strip()
    update.message.reply_text("비밀번호를 입력해주세요:")
    return PASSWORD

def get_password(update: Update, ctx: CallbackContext):
    ctx.user_data["password"] = update.message.text.strip()
    try:
        update.message.delete()
    except Exception:
        pass
    rail = ctx.user_data["rail"]
    stations = STATIONS_SRT if rail == "SRT" else STATIONS_KTX
    kb = [[s] for s in stations]
    update.message.reply_text(
        "출발역을 선택하세요:",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )
    return DEP

def get_dep(update: Update, ctx: CallbackContext):
    ctx.user_data["dep"] = update.message.text.strip()
    rail = ctx.user_data["rail"]
    stations = STATIONS_SRT if rail == "SRT" else STATIONS_KTX
    kb = [[s] for s in stations if s != ctx.user_data["dep"]]
    update.message.reply_text(
        "도착역을 선택하세요:",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )
    return ARR

def get_arr(update: Update, ctx: CallbackContext):
    ctx.user_data["arr"] = update.message.text.strip()
    update.message.reply_text("날짜를 입력하세요 (예: 20250601):",
                              reply_markup=ReplyKeyboardRemove())
    return DATE

def get_date(update: Update, ctx: CallbackContext):
    d = update.message.text.strip()
    if len(d) != 8 or not d.isdigit():
        update.message.reply_text("형식이 맞지 않아요. 예: 20250601")
        return DATE
    ctx.user_data["date"] = d
    update.message.reply_text("출발 시각 이후를 입력하세요 (예: 0600):")
    return TIME_STR

def get_time(update: Update, ctx: CallbackContext):
    ctx.user_data["dep_time"] = update.message.text.strip()
    kb = [["일반실", "특실"]]
    update.message.reply_text(
        "좌석 종류를 선택하세요:",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )
    return SEAT

def get_seat(update: Update, ctx: CallbackContext):
    ctx.user_data["seat"] = update.message.text.strip()
    kb = [["1", "2", "3", "4"]]
    update.message.reply_text(
        "인원 수를 선택하세요:",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )
    return PAX

def get_pax(update: Update, ctx: CallbackContext):
    ctx.user_data["pax"] = int(update.message.text.strip())
    d = ctx.user_data
    summary = (
        f"✅ 예매 정보 확인\n\n"
        f"노선: {d['rail']}\n"
        f"구간: {d['dep']} → {d['arr']}\n"
        f"날짜: {d['date']}\n"
        f"시각: {d['dep_time']} 이후\n"
        f"좌석: {d['seat']} {d['pax']}명\n\n"
        f"취소표 조회를 시작할까요?"
    )
    kb = [["✅ 시작", "❌ 취소"]]
    update.message.reply_text(
        summary,
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )
    return CONFIRM

def confirm(update: Update, ctx: CallbackContext):
    if "시작" not in update.message.text:
        update.message.reply_text("취소되었습니다. /start 로 다시 시작하세요.",
                                  reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    update.message.reply_text(
        "🔍 조회를 시작합니다! 취소표가 나오면 바로 알려드릴게요.\n/stop 으로 중지할 수 있어요.",
        reply_markup=ReplyKeyboardRemove()
    )

    chat_id = update.effective_chat.id
    d = dict(ctx.user_data)
    bot = ctx.bot

    stop_event = threading.Event()
    running_tasks[chat_id] = stop_event

    t = threading.Thread(target=macro_loop, args=(bot, chat_id, d, stop_event), daemon=True)
    t.start()
    return ConversationHandler.END

def stop_cmd(update: Update, ctx: CallbackContext):
    chat_id = update.effective_chat.id
    event = running_tasks.pop(chat_id, None)
    if event:
        event.set()
        update.message.reply_text("⏹ 조회가 중지되었습니다.")
    else:
        update.message.reply_text("실행 중인 조회가 없습니다.")

def cancel(update: Update, ctx: CallbackContext):
    update.message.reply_text("취소되었습니다.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def macro_loop(bot, chat_id, d, stop_event):
    attempt = 0
    while not stop_event.is_set():
        attempt += 1
        try:
            success = try_reserve(d)
            if success:
                bot.send_message(chat_id,
                    f"🎉 취소표 예매 성공!\n{d['dep']} → {d['arr']} {d['date']}\n앱에서 결제를 완료해주세요!")
                running_tasks.pop(chat_id, None)
                return
            if attempt % 10 == 0:
                bot.send_message(chat_id, f"🔍 조회 중... ({attempt}회 시도, 아직 취소표 없음)")
        except Exception as e:
            log.error(f"오류: {e}")
        stop_event.wait(30)

def try_reserve(d):
    if d["rail"] == "SRT":
        return _try_srt(d)
    else:
        return _try_ktx(d)

def _try_srt(d):
    from srt import SRT, Adult
    client = SRT(d["username"], d["password"])
    trains = client.search_train(
        dep=d["dep"], arr=d["arr"],
        date=d["date"], time=d["dep_time"],
        available_only=False
    )
    for train in trains:
        avail = train.general_seat_available() if d["seat"] == "일반실" else train.special_seat_available()
        if avail:
            client.reserve(train, passengers=[Adult()] * d["pax"])
            return True
    return False

def _try_ktx(d):
    from korail2 import Korail, AdultPassenger, TrainType
    client = Korail(d["username"], d["password"])
    trains = client.search_train(
        dep=d["dep"], arr=d["arr"],
        date=d["date"], time=d["dep_time"],
        train_type=TrainType.KTX
    )
    for train in trains:
        avail = train.general_seat_available() if d["seat"] == "일반실" else train.special_seat_available()
        if avail:
            client.reserve(train, [AdultPassenger()] * d["pax"])
            return True
    return False

def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            RAIL:     [MessageHandler(Filters.text & ~Filters.command, get_rail)],
            USERNAME: [MessageHandler(Filters.text & ~Filters.command, get_username)],
            PASSWORD: [MessageHandler(Filters.text & ~Filters.command, get_password)],
            DEP:      [MessageHandler(Filters.text & ~Filters.command, get_dep)],
            ARR:      [MessageHandler(Filters.text & ~Filters.command, get_arr)],
            DATE:     [MessageHandler(Filters.text & ~Filters.command, get_date)],
            TIME_STR: [MessageHandler(Filters.text & ~Filters.command, get_time)],
            SEAT:     [MessageHandler(Filters.text & ~Filters.command, get_seat)],
            PAX:      [MessageHandler(Filters.text & ~Filters.command, get_pax)],
            CONFIRM:  [MessageHandler(Filters.text & ~Filters.command, confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    dp.add_handler(conv)
    dp.add_handler(CommandHandler("stop", stop_cmd))
    log.info("봇 시작!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
