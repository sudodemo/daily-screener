import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

def fetch_nse_holidays():
    """
    Fetch official NSE holidays from NSE website
    """
    
    print("🔍 Fetching NSE holidays...")
    
    # NSE holidays page
    url = "https://www.nseindia.com/resources/content/whatsnew/holidays.html"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the holiday table
        tables = soup.find_all('table')
        
        holidays_list = []
        
        # Parse tables
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows:
                cols = row.find_all('td')
                
                if len(cols) >= 2:
                    date_text = cols[0].get_text(strip=True)
                    holiday_name = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                    
                    # Try to parse date
                    try:
                        # Format: "29-Mar-2024" or "29-Mar-24"
                        holiday_date = datetime.strptime(date_text, '%d-%b-%Y').strftime('%Y-%m-%d')
                        
                        holidays_list.append({
                            'date': holiday_date,
                            'name': holiday_name
                        })
                        
                        print(f"✅ {holiday_date} - {holiday_name}")
                        
                    except ValueError:
                        # Try alternate format
                        try:
                            holiday_date = datetime.strptime(date_text, '%d-%b-%y').strftime('%Y-%m-%d')
                            holidays_list.append({
                                'date': holiday_date,
                                'name': holiday_name
                            })
                            print(f"✅ {holiday_date} - {holiday_name}")
                        except:
                            pass
        
        return {'equity_market': holidays_list}
        
    except Exception as e:
        print(f"❌ Error fetching NSE holidays: {e}")
        return None


def save_holidays_to_file(holidays, filename='nse_holidays.json'):
    """Save holidays to JSON file"""
    if holidays:
        with open(filename, 'w') as f:
            json.dump(holidays, f, indent=2)
        print(f"\n✅ Holidays saved to {filename}")
        print(f"📊 Total holidays: {len(holidays['equity_market'])}")
    else:
        print("❌ No holidays to save")


if __name__ == "__main__":
    holidays = fetch_nse_holidays()
    save_holidays_to_file(holidays)
