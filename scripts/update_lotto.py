"""로또 6/45 당첨번호 자동 수집 스크립트 (2026-11-22 개정)

- data/lotto.json 의 최신 회차 이후 '놓친 회차'를 모두 따라잡는다.
- 번호별 누적 횟수(totalFreq)는 history 전체에서 다시 계산한다 (하드코딩 금지).
- 데이터 검증(회차 연속성, 번호 6개·1~45·중복 없음, 합계 = 회차수 x 6)에 실패하거나
  네트워크 오류가 계속되거나, 이미 발표됐어야 할 회차가 없으면 종료코드 1로 끝나
  GitHub Actions 에서 빨간색(실패)으로 표시된다.
- 전체 재구성: python3 scripts/update_lotto.py --rebuild
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

DATA_PATH = os.path.join("data", "lotto.json")
API_URL = "https://www.dhlottery.co.kr/lt645/selectPstLt645Info.do?srchLtEpsd={round_no}"
KST = timezone(timedelta(hours=9))
FIRST_DRAW = datetime(2002, 12, 7, 20, 35, tzinfo=KST)  # 제1회 추첨
PUBLISH_GRACE = timedelta(hours=2)  # 추첨 후 이 시간이 지나면 결과가 있어야 함
MAX_CATCHUP = 2000


class FetchError(Exception):
    pass


def format_prize(amount):
    if not amount:
        return "정보 없음"
    eok = amount // 100_000_000
    man = (amount % 100_000_000) // 10_000
    if eok > 0:
        return f"약 {eok}억 {man:,}만 원"
    return f"약 {man:,}만 원"


def fetch_draw(round_no, retries=3):
    """회차 데이터를 반환. 아직 발표 전이면 None. 통신·형식 오류가 계속되면 FetchError."""
    url = API_URL.format(round_no=round_no) + f"&_={int(time.time() * 1000)}"
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; LottoUpdater/2.0)",
                "Referer": "https://www.dhlottery.co.kr/lt645/result",
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            items = (raw.get("data") or {}).get("list")
            if items is None:
                raise FetchError(f"예상치 못한 응답 형식: {str(raw)[:200]}")
            if not items:
                return None
            return parse_item(items[0], round_no)
        except FetchError:
            raise
        except Exception as e:  # 네트워크·JSON 오류는 재시도
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise FetchError(f"{round_no}회 조회 실패: {last_err}")


def parse_item(item, round_no):
    if int(item.get("ltEpsd", -1)) != int(round_no):
        raise FetchError(f"요청 {round_no}회와 응답 회차 {item.get('ltEpsd')} 불일치")
    nums = [item.get(f"tm{i}WnNo") for i in range(1, 7)]
    bonus = item.get("bnsWnNo")
    raw_date = str(item.get("ltRflYmd") or "")
    if len(raw_date) != 8 or not raw_date.isdigit():
        raise FetchError(f"{round_no}회 날짜 형식 오류: {raw_date}")
    return {
        "round": int(round_no),
        "date": f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}",
        "numbers": sorted(int(n) for n in nums),
        "bonus": int(bonus),
        "winners": int(item.get("rnk1WnNope") or 0),
        "prize": format_prize(int(item.get("rnk1WnAmt") or 0)),
    }


def validate_draw(d):
    nums = d["numbers"]
    if len(nums) != 6 or len(set(nums)) != 6 or not all(1 <= n <= 45 for n in nums):
        raise ValueError(f"{d['round']}회 번호 오류: {nums}")
    if not (1 <= d["bonus"] <= 45) or d["bonus"] in nums:
        raise ValueError(f"{d['round']}회 보너스 오류: {d['bonus']}")


def compute_total_freq(history):
    freq = {str(n): 0 for n in range(1, 46)}
    for d in history:
        for n in d["numbers"]:
            freq[str(n)] += 1
    return freq


def validate_all(history, total_freq):
    rounds = [d["round"] for d in history]
    expected = list(range(len(history), 0, -1))
    if rounds != expected:
        raise ValueError("회차가 1회부터 연속되지 않거나 정렬이 잘못됨")
    for d in history:
        validate_draw(d)
    s = sum(total_freq.values())
    if s != len(history) * 6:
        raise ValueError(f"누적 합계 {s} != 회차수 {len(history)} x 6")


def expected_latest_round(now=None):
    """현재 시각 기준으로 이미 발표됐어야 하는 최신 회차."""
    now = now or datetime.now(KST)
    weeks = (now - FIRST_DRAW - PUBLISH_GRACE) // timedelta(weeks=1)
    return int(weeks) + 1


def save(history):
    total_freq = compute_total_freq(history)
    validate_all(history, total_freq)
    payload = {
        "source": "동행복권 공식 당첨번호 (dhlottery.co.kr)",
        "updatedAt": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "latestRound": history[0]["round"],
        "drawCount": len(history),
        "totalFreq": total_freq,
        "history": history,
    }
    # 한 회차당 한 줄로 저장 (용량 절약 + diff 가독성)
    lines = ['{']
    for key in ("source", "updatedAt", "latestRound", "drawCount", "totalFreq"):
        lines.append(f'  {json.dumps(key)}: {json.dumps(payload[key], ensure_ascii=False)},')
    lines.append('  "history": [')
    lines.append(",\n".join("    " + json.dumps(d, ensure_ascii=False) for d in history))
    lines.append('  ]')
    lines.append('}')
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    rebuild = "--rebuild" in sys.argv
    history = []
    if not rebuild and os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            history = json.load(f).get("history", [])
        history.sort(key=lambda d: d["round"], reverse=True)
        if not history or history[-1]["round"] != 1:
            print("기존 데이터가 1회부터 연속되지 않아 전체 재구성합니다.")
            history = []

    latest = history[0]["round"] if history else 0
    added = []
    try:
        for round_no in range(latest + 1, latest + 1 + MAX_CATCHUP):
            draw = fetch_draw(round_no)
            if draw is None:
                break
            validate_draw(draw)
            added.append(draw)
            if rebuild:
                time.sleep(0.05)
    except (FetchError, ValueError) as e:
        print(f"::error::{e}")
        if added:  # 받은 데까지는 저장
            history = sorted(added, key=lambda d: d["round"], reverse=True) + history
            save(history)
        sys.exit(1)

    if added:
        history = sorted(added, key=lambda d: d["round"], reverse=True) + history
        save(history)
        print(f"추가된 회차: {[d['round'] for d in added][:5]}{'...' if len(added) > 5 else ''} (총 {len(added)}개)")
    else:
        # 새 회차가 없어도 기존 데이터를 다시 검증
        validate_all(history, compute_total_freq(history))
        print(f"새 회차 없음 (최신 {latest}회).")

    current = history[0]["round"]
    expect = expected_latest_round()
    print(f"저장된 최신 회차: {current}회 / 발표됐어야 할 회차: {expect}회")
    if current < expect:
        print(f"::error::{expect}회가 아직 반영되지 않았습니다. API 응답 또는 주소 변경을 확인하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
