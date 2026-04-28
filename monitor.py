"""
VCA フリヴォル 在庫監視スクリプト（GitHub Actions クラウド版）
─────────────────────────────────────────
動作方式：1時間に1回ジョブ起動 → 内部で2分ごとにループ
実質チェック間隔：約2分
PC不要・24時間稼働・完全無料（Public リポジトリ）
"""

import requests
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime, timezone, timedelta

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# 1ジョブあたりのループ時間（秒）
# GitHub Actions のタイムアウト6時間より十分短く、
# かつ次のジョブと重複しないよう55分に設定
LOOP_DURATION_SEC = 55 * 60   # 55分
CHECK_INTERVAL_SEC = 2 * 60   # 2分ごとにチェック

TARGET_URLS = {
    # ── スモール ──────────────────────────────
    "フリヴォル スモール YG": "https://www.vancleefarpels.com/jp/ja/collections/jewelry/flora/frivole/vcarb65700---frivole-earrings-small-model.html",
    "フリヴォル スモール WG": "https://www.vancleefarpels.com/jp/ja/collections/jewelry/flora/frivole/vcard80200---frivole-earrings-small-model.html",
    "フリヴォル スモール RG": "https://www.vancleefarpels.com/jp/ja/collections/jewelry/flora/frivole/vcarb65r00---frivole-earrings-small-model.html",
    # ── ミニ ──────────────────────────────────
    "フリヴォル ミニ YG":    "https://www.vancleefarpels.com/jp/ja/collections/jewelry/flora/frivole/vcarp24200---frivole-earrings-mini-model.html",
    "フリヴォル ミニ WG":    "https://www.vancleefarpels.com/jp/ja/collections/jewelry/flora/frivole/vcarp0j600---frivole-earrings-mini-model.html",
    "フリヴォル ミニ RG":    "https://www.vancleefarpels.com/jp/ja/collections/jewelry/flora/frivole/vcarp7rj00---frivole-earrings-mini-model.html",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

JST = timezone(timedelta(hours=9))


def now_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")


def send_discord(message: str) -> None:
    if not DISCORD_WEBHOOK_URL:
        print(f"[Discord未設定] {message}")
        return
    try:
        r = requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": message},
            timeout=10,
        )
        print(f"[Discord送信] status={r.status_code}")
    except Exception as e:
        print(f"[Discordエラー] {e}")


def check(name: str, url: str) -> bool:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text()

        buy_signals = ["カートに入れる", "Add to bag", "カートへ", "購入する", "add to bag"]
        if any(s.lower() in text.lower() for s in buy_signals):
            return True
        if soup.find(attrs={"data-action": "add-to-cart"}):
            return True
        if soup.find(attrs={"class": lambda c: c and "add-to-cart" in " ".join(c)}):
            return True
        return False
    except Exception as e:
        print(f"[チェックエラー] {name}: {e}")
        return False


def run_once() -> bool:
    """全URLをチェック。1件でも在庫ありならTrueを返す"""
    t = now_jst()
    print(f"\n[{t}] チェック実行")
    found = False
    for name, url in TARGET_URLS.items():
        available = check(name, url)
        print(f"  {'🟢' if available else '🔴'} {name}")
        if available:
            found = True
            send_discord(
                f"\n🚨【緊急】VCA在庫出現！\n"
                f"「{name}」が購入できます！\n"
                f"今すぐ👇\n{url}\n"
                f"検知: {t}"
            )
    return found


def main():
    print("=" * 50)
    print(f"VCA監視開始: {now_jst()}")
    print(f"チェック間隔: {CHECK_INTERVAL_SEC // 60}分 / 稼働時間: {LOOP_DURATION_SEC // 60}分")
    print("=" * 50)

    start = time.time()
    count = 0

    while time.time() - start < LOOP_DURATION_SEC:
        count += 1
        print(f"\n--- 第{count}回チェック ---")
        run_once()

        elapsed = time.time() - start
        remaining = LOOP_DURATION_SEC - elapsed
        if remaining <= CHECK_INTERVAL_SEC:
            print(f"\n残り{remaining:.0f}秒。このジョブを終了します。")
            break

        print(f"次のチェックまで{CHECK_INTERVAL_SEC // 60}分待機...")
        time.sleep(CHECK_INTERVAL_SEC)

    print(f"\n[{now_jst()}] ジョブ終了（計{count}回チェック）")


def test_notification():
    """Discord通知の動作確認用テスト送信"""
    print("テストモードで起動します...")
    msg = "[VCA監視テスト] 通知の動作確認です。このメッセージが届いていれば設定は完璧です！ 確認時刻: " + now_jst()
    send_discord(msg)
    print("テスト送信完了。Discordを確認してください。")


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        test_notification()
    else:
        main()
