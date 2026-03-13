from flask import Flask, render_template, request, redirect, url_for, flash, session
import boto3
import uuid
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = "stocker_secret_2024"

# ================= AWS CONFIGURATION =================

AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')

# Check for local development credentials
AWS_ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

if AWS_ACCESS_KEY and AWS_SECRET_KEY:
    # Local development with explicit credentials
    session_aws = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION
    )
else:
    # EC2 instance with IAM role or default credentials
    session_aws = boto3.Session(region_name=AWS_REGION)

# DynamoDB
dynamodb = session_aws.resource('dynamodb')

# SNS
sns = session_aws.client('sns')

# DynamoDB Tables
USER_TABLE = "stocker_users"
STOCK_TABLE = "stocker_stocks"
TRANSACTION_TABLE = "stocker_transactions"
PORTFOLIO_TABLE = "stocker_portfolio"

# SNS Topics
USER_ACCOUNT_TOPIC_ARN = "arn:aws:sns:us-east-1:604665149129:StockerUserAccountTopic"
TRANSACTION_TOPIC_ARN = "arn:aws:sns:us-east-1:604665149129:StockerTransactionTopic"


# ================= HELPER CLASSES =================

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


# ================= SNS FUNCTION =================

def send_notification(topic_arn, subject, message):
    if LOCAL_MODE:
        print(f"[LOCAL MODE] Notification - {subject}: {message}")
        return
    
    try:
        sns.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message
        )
    except Exception as e:
        print("SNS Error:", e)


# ================= DATABASE FUNCTIONS =================

# Local development mode - use in-memory storage if no AWS credentials
LOCAL_MODE = not (AWS_ACCESS_KEY and AWS_SECRET_KEY)

# In-memory storage for local development
local_users = {}
local_stocks = [
    {"id": "1", "symbol": "AAPL", "name": "Apple Inc.", "price": Decimal("150.25"), "change": "+2.50"},
    {"id": "2", "symbol": "GOOGL", "name": "Alphabet Inc.", "price": Decimal("2800.00"), "change": "-15.00"},
    {"id": "3", "symbol": "MSFT", "name": "Microsoft Corp.", "price": Decimal("300.50"), "change": "+5.25"}
]
local_transactions = []
local_portfolios = {}

def get_user_by_email(email):
    if LOCAL_MODE:
        return local_users.get(email)
    else:
        table = dynamodb.Table(USER_TABLE)
        response = table.get_item(Key={'email': email})
        return response.get("Item")


def create_user(username, email, password, role):
    user = {
        "id": str(uuid.uuid4()),
        "username": username,
        "email": email,
        "password": password,
        "role": role
    }
    
    if LOCAL_MODE:
        local_users[email] = user
    else:
        table = dynamodb.Table(USER_TABLE)
        table.put_item(Item=user)
    
    return user


def get_all_stocks():
    if LOCAL_MODE:
        return local_stocks
    else:
        table = dynamodb.Table(STOCK_TABLE)
        response = table.scan()
        return response.get("Items", [])


def get_stock_by_id(stock_id):
    if LOCAL_MODE:
        for stock in local_stocks:
            if stock["id"] == stock_id:
                return stock
        return None
    else:
        table = dynamodb.Table(STOCK_TABLE)
        response = table.get_item(Key={'id': stock_id})
        return response.get("Item")


def get_traders():
    if LOCAL_MODE:
        traders = []
        for user in local_users.values():
            if user.get("role") == "trader":
                traders.append(user)
        return traders
    else:
        table = dynamodb.Table(USER_TABLE)
        response = table.scan(
            FilterExpression=Attr('role').eq("trader")
        )
        return response.get("Items", [])


def get_user_by_id(user_id):
    if LOCAL_MODE:
        for user in local_users.values():
            if user.get("id") == user_id:
                return user
        return None
    else:
        table = dynamodb.Table(USER_TABLE)
        response = table.scan(
            FilterExpression=Attr('id').eq(user_id)
        )
        users = response.get("Items", [])
        return users[0] if users else None


def get_transactions():
    if LOCAL_MODE:
        transactions = local_transactions.copy()
        for t in transactions:
            t["user"] = get_user_by_id(t["user_id"])
            t["stock"] = get_stock_by_id(t["stock_id"])
        return transactions
    else:
        table = dynamodb.Table(TRANSACTION_TABLE)
        transactions = table.scan().get("Items", [])
        for t in transactions:
            t["user"] = get_user_by_id(t["user_id"])
            t["stock"] = get_stock_by_id(t["stock_id"])
        return transactions


def get_portfolios():
    if LOCAL_MODE:
        portfolios = []
        for key, portfolio in local_portfolios.items():
            p = portfolio.copy()
            p["user"] = get_user_by_id(p["user_id"])
            p["stock"] = get_stock_by_id(p["stock_id"])
            portfolios.append(p)
        return portfolios
    else:
        table = dynamodb.Table(PORTFOLIO_TABLE)
        portfolios = table.scan().get("Items", [])
        for p in portfolios:
            p["user"] = get_user_by_id(p["user_id"])
            p["stock"] = get_stock_by_id(p["stock_id"])
        return portfolios


def get_user_portfolio(user_id):
    if LOCAL_MODE:
        portfolio = []
        for key, item in local_portfolios.items():
            if item.get("user_id") == user_id:
                p = item.copy()
                p["stock"] = get_stock_by_id(p["stock_id"])
                portfolio.append(p)
        return portfolio
    else:
        table = dynamodb.Table(PORTFOLIO_TABLE)
        response = table.query(
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
        portfolio = response.get("Items", [])
        for p in portfolio:
            p["stock"] = get_stock_by_id(p["stock_id"])
        return portfolio


def get_portfolio_item(user_id, stock_id):

    if LOCAL_MODE:

        key = f"{user_id}_{stock_id}"

        return local_portfolios.get(key)

    else:

        table = dynamodb.Table(PORTFOLIO_TABLE)

        response = table.get_item(

            Key={

                "user_id": user_id,

                "stock_id": stock_id

            }

        )

        return response.get("Item")


def create_transaction(user_id, stock_id, action, quantity, price):

    transaction = {

        "id": str(uuid.uuid4()),

        "user_id": user_id,

        "stock_id": stock_id,

        "action": action,

        "quantity": Decimal(str(quantity)),

        "price": Decimal(str(price)),

        "status": "completed",

        "transaction_date": datetime.now().isoformat()
    }

    if LOCAL_MODE:

        local_transactions.append(transaction)

    else:

        table = dynamodb.Table(TRANSACTION_TABLE)

        table.put_item(Item=transaction)

    return transaction


def update_portfolio(user_id, stock_id, quantity, average_price):

    quantity = Decimal(str(quantity))

    average_price = Decimal(str(average_price))

    if LOCAL_MODE:

        key = f"{user_id}_{stock_id}"

        if quantity > 0:

            local_portfolios[key] = {

                "user_id": user_id,

                "stock_id": stock_id,

                "quantity": quantity,

                "average_price": average_price

            }

        else:

            local_portfolios.pop(key, None)

    else:

        table = dynamodb.Table(PORTFOLIO_TABLE)

        existing = get_portfolio_item(user_id, stock_id)

        if existing and quantity > 0:

            table.update_item(

                Key={"user_id": user_id, "stock_id": stock_id},

                UpdateExpression="set quantity=:q, average_price=:p",

                ExpressionAttributeValues={

                    ":q": quantity,

                    ":p": average_price
                }
            )

        elif existing and quantity <= 0:

            table.delete_item(

                Key={"user_id": user_id, "stock_id": stock_id}
            )

        elif quantity > 0:

            table.put_item(

                Item={

                    "user_id": user_id,

                    "stock_id": stock_id,

                    "quantity": quantity,

                    "average_price": average_price
                }
            )


# ================= ROUTES =================

@app.route('/')
def index():
    return render_template("index.html")


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        print(f"[DEBUG] Login form submitted: {request.form}")
        
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]
        
        print(f"[DEBUG] Login attempt: email={email}, role={role}")
        
        user = get_user_by_email(email)
        print(f"[DEBUG] Found user: {user}")
        
        if user:
            print(f"[DEBUG] User password: {user['password']}")
            print(f"[DEBUG] User role: {user['role']}")
            print(f"[DEBUG] Provided password: {password}")
            print(f"[DEBUG] Provided role: {role}")
            print(f"[DEBUG] Password match: {user['password'] == password}")
            print(f"[DEBUG] Role match: {user['role'] == role}")
        
        if user and user["password"] == password and user["role"] == role:
            print(f"[DEBUG] Login successful for {user['username']}")
            
            session["email"] = user["email"]
            session["role"] = user["role"]
            session["user_id"] = user["id"]

            send_notification(
                USER_ACCOUNT_TOPIC_ARN,
                "User Login",
                f"{user['username']} logged in"
            )

            if role == "admin":
                print(f"[DEBUG] Redirecting to admin dashboard")
                return redirect(url_for("dashboard_admin"))
            else:
                print(f"[DEBUG] Redirecting to trader dashboard")
                return redirect(url_for("dashboard_trader"))

        print(f"[DEBUG] Login failed - invalid credentials")
        flash("Invalid credentials")

    return render_template("login.html")


@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        print(f"[DEBUG] Signup form submitted: {request.form}")
        
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]
        
        print(f"[DEBUG] Extracted: username={username}, email={email}, role={role}")

        if get_user_by_email(email):
            print(f"[DEBUG] User already exists: {email}")
            flash("User already exists")
            return redirect(url_for("login"))

        create_user(username, email, password, role)
        print(f"[DEBUG] User created successfully: {username}")

        send_notification(
            USER_ACCOUNT_TOPIC_ARN,
            "New User Signup",
            f"{username} created an account"
        )
        
        print(f"[DEBUG] Redirecting to login")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route('/dashboard_admin')
def dashboard_admin():

    stocks = get_all_stocks()

    user = get_user_by_email(session["email"])

    return render_template(

        "dashboard_admin.html",

        user=user,

        market_data=stocks
    )


@app.route('/dashboard_trader')
def dashboard_trader():

    stocks = get_all_stocks()

    user = get_user_by_email(session["email"])

    return render_template(

        "dashboard_trader.html",

        user=user,

        market_data=stocks
    )


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route('/service01')
def service01():
    traders = get_traders()
    return render_template("service01.html", traders=traders)


@app.route('/service02')
def service02():
    transactions = get_transactions()
    return render_template("service02.html", transactions=transactions)


@app.route('/service03')
def service03():
    portfolios = get_portfolios()
    return render_template("service03.html", portfolios=portfolios)


@app.route('/service04')
def service04():
    stocks = get_all_stocks()
    return render_template("service04.html", stocks=stocks)


@app.route('/service05')
def service05():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user_portfolio = get_user_portfolio(user_id)
    user_transactions = [t for t in get_transactions() if t.get('user_id') == user_id]
    
    return render_template("service05.html", portfolio=user_portfolio, transactions=user_transactions)


@app.route('/buy_stock/<stock_id>', methods=['GET', 'POST'])
def buy_stock(stock_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    stock = get_stock_by_id(stock_id)
    if not stock:
        flash("Stock not found")
        return redirect(url_for('service04'))
    
    if request.method == 'POST':
        quantity = int(request.form.get('quantity', 0))
        if quantity > 0:
            price = Decimal(str(stock['price']))
            create_transaction(session['user_id'], stock_id, 'buy', quantity, price)
            
            portfolio_item = get_portfolio_item(session['user_id'], stock_id)
            if portfolio_item:
                current_qty = Decimal(str(portfolio_item.get('quantity', 0)))
                current_avg_price = Decimal(str(portfolio_item.get('average_price', 0)))
                new_qty = current_qty + Decimal(str(quantity))
                new_avg_price = ((current_qty * current_avg_price) + (Decimal(str(quantity)) * price)) / new_qty
            else:
                new_qty = Decimal(str(quantity))
                new_avg_price = price
                
            update_portfolio(session['user_id'], stock_id, new_qty, new_avg_price)
            flash("Successfully bought stock!")
            return redirect(url_for('service05'))
        else:
            flash("Invalid quantity")

    return render_template("buy_stock.html", stock=stock)


@app.route('/sell_stock/<stock_id>', methods=['GET', 'POST'])
def sell_stock(stock_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    stock = get_stock_by_id(stock_id)
    if not stock:
        flash("Stock not found")
        return redirect(url_for('service04'))
        
    portfolio_entry = get_portfolio_item(session['user_id'], stock_id)
    if not portfolio_entry:
        flash("You do not own this stock")
        return redirect(url_for('service05'))
        
    if request.method == 'POST':
        quantity = int(request.form.get('quantity', 0))
        current_qty = int(portfolio_entry.get('quantity', 0))
        if 0 < quantity <= current_qty:
            price = Decimal(str(stock['price']))
            create_transaction(session['user_id'], stock_id, 'sell', quantity, price)
            
            new_qty = Decimal(str(current_qty - quantity))
            avg_price = Decimal(str(portfolio_entry.get('average_price', 0)))
            update_portfolio(session['user_id'], stock_id, new_qty, avg_price)
            flash("Successfully sold stock!")
            return redirect(url_for('service05'))
        else:
            flash("Invalid quantity")
    
    return render_template("sell_stock.html", stock=stock, portfolio_entry=portfolio_entry)


# ================= RUN =================

if __name__ == "__main__":

    app.run(debug=True, host="0.0.0.0", port=5000)