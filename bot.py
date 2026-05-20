import os
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
 
