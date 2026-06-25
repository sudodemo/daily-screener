from playwright.sync_api import sync_playwright
import time, json, os, requests, datetime

# ================= CONFIG =================
SCANNERS = {
    "Daily Bullish Stocks to Buy": "https://chartink.com/screener/sandeepm-daily-bullish-crossover-cash",
    "Daily Bearish Stocks to Sell": "https://chartink.com/screener/sandeepm-daily-bearish-crossover-cash-2",
    "Weekly Bullish Stocks to Buy": "https://chartink.com/screener/sandeepm-weekly-bullish-crossover-1",
    "Weekly Bearish Stocks to Sell": "https://chartink.com/screener/sandeepm-weekly-bearish-crossover-indices",
    "Monthly Bullish Stocks to Buy": "https://chartink.com/screener/sandeepm-monthly-bullish-crossover",
    "Quarterly Bullish Stocks to Buy": "https://chartink.com/screener/sm-quarterly-crossover-5-10-20-ema-crossover-check-every-quarter-end"
}

DATA_FILE = "seen_stocks.json"
HOLIDAYS_FILE = "nse_holidays.json"

# ===== TELEGRAM =====
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram(msg):
    """Send alert via Telegram"""
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram credentials not set")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        response = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": msg,
                "parse_mode": "HTML"
            },
            timeout=10
        )
        if response.status_code == 200:
            print(f"✅ Telegram message sent!")
            return True
        else:
            print(f"❌ Telegram error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Telegram Error: {e}")
        return False


# ===== LOAD HOLIDAYS FROM JSON =====
def load_holidays():
    """Load NSE holidays from JSON file"""
    if os.path.exists(HOLIDAYS_FILE):
        try:
            with open(HOLIDAYS_FILE, "r") as f:
                data = json.load(f)
                holidays_list = data.get('equity_market', [])
                # Convert to set of date strings for faster lookup
                return set(h['date'] for h in holidays_list)
        except Exception as e:
            print(f"⚠️ Error loading holidays: {e}")
            return set()
    else:
        print(f"⚠️ {HOLIDAYS_FILE} not found - using hardcoded holidays")
        return set()


HOLIDAYS = load_holidays()


def is_market_holiday(date):
    """Check if date is a market holiday"""
    date_str = date.strftime("%Y-%m-%d")
    return date_str in HOLIDAYS


def is_market_open():
    """
    Check if market is open:
    1. Not a holiday
    2. Not a weekend
    3. Within market hours (9:15 AM - 3:30 PM IST)
    """
    now = datetime.datetime.now()
    ist_time = now + datetime.timedelta(hours=5, minutes=30)
    
    # Check if it's a weekend
    if ist_time.weekday() >= 5:  # Saturday=5, Sunday=6
        return False, "Weekend"
    
    # Check if it's a holiday
    if is_market_holiday(ist_time.date()):
        holiday_name = get_holiday_name(ist_time.date())
        return False, f"Market Holiday ({holiday_name})"
    
    # Check if within market hours
    market_open = datetime.time(9, 15)
    market_close = datetime.time(15, 30)
    
    if not (market_open <= ist_time.time() <= market_close):
        return False, "Market Closed (Outside Hours)"
    
    return True, "Market Open"


def get_holiday_name(date):
    """Get the name of the holiday"""
    if os.path.exists(HOLIDAYS_FILE):
        try:
            with open(HOLIDAYS_FILE, "r") as f:
                data = json.load(f)
                date_str = date.strftime("%Y-%m-%d")
                for holiday in data.get('equity_market', []):
                    if holiday['date'] == date_str:
                        return holiday['name']
        except:
            pass
    return "Market Holiday"


# ===== STATE =====
def load_seen():
    """Load previously seen stocks"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_seen(data):
    """Save seen stocks to file"""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ===== SCRAPER =====
def fetch_all_scanners(browser):
    """Fetch stocks from all scanners"""
    context = browser.new_context()
    results = {}

    for name, url in SCANNERS.items():
        try:
            page = context.new_page()
            print(f"🔍 Loading {name}...")

            page.goto(url, timeout=60000)
            page.wait_for_selector("table tbody tr", timeout=60000)

            rows = page.query_selector_all("table tbody tr")
            stocks = []

            for row in rows:
                cols = row.query_selector_all("td")
                if len(cols) > 6:
                    symbol = cols[2].inner_text().strip()
                    close = cols[3].inner_text().strip()
                    
                    stocks.append({
                        "symbol": symbol,
                        "close": close,
                    })

            results[name] = stocks
            print(f"✅ Fetched {len(stocks)} stocks from {name}")
            page.close()

        except Exception as e:
            print(f"❌ Error in {name}: {e}")
            results[name] = []

    context.close()
    return results


# ===== MAIN BOT =====
def run():
    print("=" * 60)
    print("🚀 ALERTS STARTED")
    now = datetime.datetime.now()
    ist_time = now + datetime.timedelta(hours=5, minutes=30)
    print(f"⏰ UTC Time: {now}")
    print(f"⏰ IST Time: {ist_time}")
    print(f"📅 Loaded {len(HOLIDAYS)} holidays from NSE")
    print("=" * 60)
    
    # Check if market is open
    is_open, reason = is_market_open()
    
    print(f"📊 Market Status: {reason}")
    
    if not is_open:
        print(f"🛑 Stopping bot - {reason}")
        send_telegram(f"🛑 Alerts paused - {reason}")
        return
    
    send_telegram("🤖 Alerts started")

    seen = load_seen()
    first_run = True

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]
        )

        try:
            all_data = fetch_all_scanners(browser)

            for name, stocks in all_data.items():

                if name not in seen:
                    seen[name] = []

                new_stocks = []

                for s in stocks:
                    if first_run or s["symbol"] not in seen[name]:
                        new_stocks.append(s)

                if new_stocks:
                    msg = f"<b>🚨 {name} Alert</b>\n\n"
                    for s in new_stocks:
                        msg += f"<code>{s['symbol']}</code> | ₹{s['close']}\n"

                    print(msg)
                    send_telegram(msg)
                else:
                    print(f"ℹ️ No new stocks in {name}")

                seen[name] = [s["symbol"] for s in stocks]

            save_seen(seen)
            first_run = False
            print("\n✅ Scan completed successfully!")

        except Exception as e:
            print(f"🔥 Error: {e}")
            send_telegram(f"🔥 Error: {str(e)}")
            import traceback
            traceback.print_exc()

        finally:
            browser.close()


if __name__ == "__main__":
    run()
