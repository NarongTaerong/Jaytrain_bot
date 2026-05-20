import os
import asyncio
import logging
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

log = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN 환경변수가 없습니다.")

ALLOWED_USER_ID = int(os.environ.get("ALLOWED_USER_ID", "0"))

(
    RAIL,
    USERNAME,
    PASSWORD,
    DEP,
    ARR,
    DATE,
    TIME_STR,
    SEAT,
    PAX,
    CONFIRM,
) = range(10)

STATIONS_SRT = [
    "수서", "동탄", "평택지제", "천안아산", "오송", "대전",
    "김천구미", "동대구", "경주", "울산", "부산",
    "광주송정", "목포", "여수EXPO"
]

STATIONS_KTX = [
    "서울", "용산", "광명", "수원", "천안아산", "오송",
    "대전", "김천구미", "동대구", "경주",
    "울산(통도사)", "부산", "마산", "광주송정",
    "목포", "강릉"
]


# ─────────────────────────────────────
# 권한 확인
# ─────────────────────────────────────
def is_allowed(update: Update) -> bool:
    if ALLOWED_USER_ID == 0:
        return True

    return update.effective_user.id == ALLOWED_USER_ID


# ─────────────────────────────────────
# /start
# ─────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await update.message.reply_text("❌ 권한이 없습니다.")
        return ConversationHandler.END

    kb = [["SRT", "코레일 KTX"]]

    await update.message.reply_text(
        "🚄 기차 취소표 자동 예매 봇\n\n어떤 기차를 예매하시겠어요?",
        reply_markup=ReplyKeyboardMarkup(
            kb,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return RAIL


async def get_rail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()

    if txt not in ["SRT", "코레일 KTX"]:
        await update.message.reply_text("SRT 또는 코레일 KTX를 선택해주세요.")
        return RAIL

    ctx.user_data["rail"] = "SRT" if txt == "SRT" else "KTX"

    await update.message.reply_text(
        "🔐 아이디(회원번호 또는 이메일)를 입력해주세요:",
        reply_markup=ReplyKeyboardRemove(),
    )

    return USERNAME


async def get_username(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["username"] = update.message.text.strip()

    await update.message.reply_text(
        "🔑 비밀번호를 입력해주세요:\n(입력 후 메시지는 삭제 권장)"
    )

    return PASSWORD


async def get_password(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["password"] = update.message.text.strip()

    try:
        await update.message.delete()
    except Exception:
        pass

    rail = ctx.user_data["rail"]

    stations = STATIONS_SRT if rail == "SRT" else STATIONS_KTX

    kb = [[s] for s in stations]

    await update.message.reply_text(
        "🚉 출발역 선택",
        reply_markup=ReplyKeyboardMarkup(
            kb,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return DEP


async def get_dep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    dep = update.message.text.strip()

    ctx.user_data["dep"] = dep

    rail = ctx.user_data["rail"]

    stations = STATIONS_SRT if rail == "SRT" else STATIONS_KTX

    kb = [[s] for s in stations if s != dep]

    await update.message.reply_text(
        "🚉 도착역 선택",
        reply_markup=ReplyKeyboardMarkup(
            kb,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return ARR


async def get_arr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["arr"] = update.message.text.strip()

    await update.message.reply_text(
        "📅 날짜 입력 (예: 20260601)",
        reply_markup=ReplyKeyboardRemove(),
    )

    return DATE


async def get_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    d = update.message.text.strip()

    try:
        datetime.strptime(d, "%Y%m%d")
    except ValueError:
        await update.message.reply_text(
            "❌ 날짜 형식 오류\n예: 20260601"
        )
        return DATE

    ctx.user_data["date"] = d

    await update.message.reply_text(
        "⏰ 출발 시각 입력 (예: 0600)"
    )

    return TIME_STR


async def get_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip()

    if len(t) != 4 or not t.isdigit():
        await update.message.reply_text("❌ 예: 0600 형식으로 입력")
        return TIME_STR

    hh = int(t[:2])
    mm = int(t[2:])

    if hh > 23 or mm > 59:
        await update.message.reply_text("❌ 잘못된 시간입니다")
        return TIME_STR

    ctx.user_data["dep_time"] = t

    kb = [["일반실", "특실"]]

    await update.message.reply_text(
        "💺 좌석 종류 선택",
        reply_markup=ReplyKeyboardMarkup(
            kb,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return SEAT


async def get_seat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["seat"] = update.message.text.strip()

    kb = [["1", "2", "3", "4"]]

    await update.message.reply_text(
        "👥 인원 수 선택",
        reply_markup=ReplyKeyboardMarkup(
            kb,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return PAX


async def get_pax(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["pax"] = int(update.message.text.strip())

    d = ctx.user_data

    summary = (
        f"✅ 예매 정보\n\n"
        f"노선: {d['rail']}\n"
        f"구간: {d['dep']} → {d['arr']}\n"
        f"날짜: {d['date']}\n"
        f"시간: {d['dep_time']} 이후\n"
        f"좌석: {d['seat']}\n"
        f"인원: {d['pax']}명\n\n"
        f"조회 시작할까요?"
    )

    kb = [["✅ 시작", "❌ 취소"]]

    await update.message.reply_text(
        summary,
        reply_markup=ReplyKeyboardMarkup(
            kb,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return CONFIRM


async def confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if "시작" not in update.message.text:
        await update.message.reply_text(
            "취소되었습니다.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🔍 조회 시작\n/stop 으로 중지 가능",
        reply_markup=ReplyKeyboardRemove(),
    )

    chat_id = update.effective_chat.id

    d = dict(ctx.user_data)

    task = asyncio.create_task(
        macro_loop(ctx.application, chat_id, d)
    )

    ctx.application.bot_data.setdefault("tasks", {})[chat_id] = task

    return ConversationHandler.END


# ─────────────────────────────────────
# /stop
# ─────────────────────────────────────
async def stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    tasks = ctx.application.bot_data.get("tasks", {})

    task = tasks.pop(chat_id, None)

    if task:
        task.cancel()
        await update.message.reply_text("⏹ 조회 중지")
    else:
        await update.message.reply_text("실행 중인 조회 없음")


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "취소되었습니다.",
        reply_markup=ReplyKeyboardRemove(),
    )

    return ConversationHandler.END


# ─────────────────────────────────────
# 조회 루프
# ─────────────────────────────────────
async def macro_loop(app, chat_id: int, d: dict):
    attempt = 0

    try:
        while True:
            attempt += 1

            try:
                success = await asyncio.to_thread(try_reserve, d)

                if success:
                    await app.bot.send_message(
                        chat_id,
                        (
                            f"🎉 예매 성공!\n"
                            f"{d['dep']} → {d['arr']}\n"
                            f"{d['date']}"
                        ),
                    )
                    return

                if attempt % 10 == 0:
                    await app.bot.send_message(
                        chat_id,
                        f"🔍 조회 중... ({attempt}회 시도)",
                    )

            except Exception as e:
                log.exception(e)

                await app.bot.send_message(
                    chat_id,
                    "⚠️ 일시적 오류 발생. 재시도합니다."
                )

            await asyncio.sleep(30)

    except asyncio.CancelledError:
        log.info(f"조회 중지: {chat_id}")

    finally:
        app.bot_data.get("tasks", {}).pop(chat_id, None)


# ─────────────────────────────────────
# 예매 시도
# ─────────────────────────────────────
def try_reserve(d: dict) -> bool:
    if d["rail"] == "SRT":
        return _try_srt(d)

    return _try_ktx(d)


# ─────────────────────────────────────
# SRT
# ─────────────────────────────────────
def _try_srt(d: dict) -> bool:
    from srt import SRT, Adult

    client = SRT(d["username"], d["password"])

    trains = client.search_train(
        dep=d["dep"],
        arr=d["arr"],
        date=d["date"],
        time=d["dep_time"],
        available_only=False,
    )

    for train in trains:
        if d["seat"] == "일반실":
            avail = train.general_seat_available()
        else:
            avail = train.special_seat_available()

        if avail:
            passengers = [Adult()] * d["pax"]
            client.reserve(train, passengers=passengers)
            return True

    return False


# ─────────────────────────────────────
# KTX
# ─────────────────────────────────────
def _try_ktx(d: dict) -> bool:
    from korail2 import Korail, AdultPassenger, TrainType

    client = Korail(d["username"], d["password"])

    trains = client.search_train(
        dep=d["dep"],
        arr=d["arr"],
        date=d["date"],
        time=d["dep_time"],
        train_type=TrainType.KTX,
    )

    for train in trains:
        if d["seat"] == "일반실":
            avail = train.general_seat_available()
        else:
            avail = train.special_seat_available()

        if avail:
            passengers = [AdultPassenger()] * d["pax"]
            client.reserve(train, passengers)
            return True

    return False


# ─────────────────────────────────────
# 실행
# ─────────────────────────────────────
def main():
    app = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            RAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rail)],
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            DEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_dep)],
            ARR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_arr)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            TIME_STR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            SEAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_seat)],
            PAX: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pax)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("stop", stop))

    log.info("봇 시작")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
