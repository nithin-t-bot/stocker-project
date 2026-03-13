import requests
from bs4 import BeautifulSoup

BASE_URL = "http://localhost:5000"

def run_tests():
    s = requests.Session()
    
    # 1. Signup
    print("Testing Signup...")
    res = s.post(f"{BASE_URL}/signup", data={
        "username": "testuser",
        "email": "test@user.com",
        "password": "password123",
        "role": "trader"
    })
    print("Signup status:", res.status_code)

    # 2. Login
    print("Testing Login...")
    res = s.post(f"{BASE_URL}/login", data={
        "email": "test@user.com",
        "password": "password123",
        "role": "trader"
    })
    print("Login status:", res.status_code)
    
    # 3. View Trader Dashboard
    print("Testing Trader Dashboard...")
    res = s.get(f"{BASE_URL}/dashboard_trader")
    if res.status_code != 200:
        print("Error Trader Dashboard!")
    else:
        print("Trader Dashboard loaded successfully.")
        
    # 4. View Stocks (service04)
    res = s.get(f"{BASE_URL}/service04")
    if res.status_code == 200:
        print("Stocks list loaded.")
        
    # 5. Buy Stock (Apple id: 1)
    print("Testing Buy Stock...")
    res = s.post(f"{BASE_URL}/buy_stock/1", data={"quantity": 5})
    if res.status_code == 200:
        print("Buy Stock Page instead of redirect... wait, if success it should redirect")
    print("Buy Stock response status:", res.status_code)
    
    # 6. View Portfolio (service05)
    print("Testing Portfolio...")
    res = s.get(f"{BASE_URL}/service05")
    if res.status_code == 200:
        print("Portfolio loaded. Checking if contains AAPL...")
        if "AAPL" in res.text:
            print("AAPL found in portfolio.")
        else:
            print("AAPL not found in portfolio!")
            # print(res.text) # Too long
    else:
        print("Error Portfolio:", res.status_code)
        
    # 7. Sell Stock
    print("Testing Sell Stock...")
    res = s.post(f"{BASE_URL}/sell_stock/1", data={"quantity": 2})
    print("Sell Stock response status:", res.status_code)

    # 8. View Portfolio again
    res = s.get(f"{BASE_URL}/service05")
    if "AAPL" in res.text:
        print("AAPL still in portfolio after selling partial amount.")

if __name__ == "__main__":
    run_tests()
