import json
import os
import time
import urllib.request

DATA_PATH = os.path.join("data", "lotto.json")

def format_prize(amount):
    if not amount:
        return "정보 없음"
    eok = amount // 100_000_000
    man = (amount % 100_000_000) // 10_000
    if eok > 0:
        return f"약 {eok}억 {man:,}만 원"
    return f"약 {man:,}만 원"

def fetch_draw(round_no):
    url = f"https://www.dhlottery.co.kr/lt645/selectPstLt645Info.do?srchLtEpsd={round_no}&_={int(time.time()*1000)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; LottoUpdater/1.0)",
            "Referer": "https://www.dhlottery.co.kr/lt645/result"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    item = None
    if isinstance(raw, dict):
        if "data" in raw and isinstance(raw["data"], dict) and raw["data"].get("list"):
            item = raw["data"]["list"][0]
        elif "ltEpsd" in raw or "drwNo" in raw:
            item = raw

    if not item:
        return None

    nums = [
        item.get("tm1WnNo") or item.get("drwtNo1"),
        item.get("tm2WnNo") or item.get("drwtNo2"),
        item.get("tm3WnNo") or item.get("drwtNo3"),
        item.get("tm4WnNo") or item.get("drwtNo4"),
        item.get("tm5WnNo") or item.get("drwtNo5"),
        item.get("tm6WnNo") or item.get("drwtNo6"),
    ]
    bonus = item.get("bnsWnNo") or item.get("bnusNo")
    if not all(nums) or not bonus:
        return None

    raw_date = str(item.get("ltRflYmd") or item.get("drwNoDate") or "")
    date_str = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}" if len(raw_date) == 8 and raw_date.isdigit() else raw_date
    winners = int(item.get("rnk1WnNope") or item.get("firstPrzwnerCo") or 0)
    prize_amt = int(item.get("rnk1WnAmt") or item.get("firstWinamnt") or 0)

    return {
        "round": int(round_no),
        "date": date_str,
        "numbers": sorted(int(n) for n in nums),
        "bonus": int(bonus),
        "winners": winners,
        "prize": format_prize(prize_amt)
    }

def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    history = payload["history"]
    total_freq = payload["totalFreq"]
    latest_round = max(item["round"] for item in history)
    next_round = latest_round + 1

    try:
        new_draw = fetch_draw(next_round)
    except Exception as e:
        print(f"Fetch failed: {e}")
        return

    if not new_draw:
        print(f"Draw #{next_round} is not available yet.")
        return

    history.insert(0, new_draw)
    for n in new_draw["numbers"]:
        key = str(n)
        total_freq[key] = int(total_freq.get(key, 0)) + 1

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Updated draw #{next_round} and incremented totalFreq.")

if __name__ == "__main__":
    main()
