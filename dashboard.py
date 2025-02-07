from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
import requests
import os
from datetime import datetime, timedelta
from functools import lru_cache

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')
socketio = SocketIO(app)

# Replace with your Alpha Vantage API key
ALPHA_VANTAGE_API_KEY = os.environ.get('ALPHA_VANTAGE_API_KEY')

# 添加缓存装饰器
@lru_cache(maxsize=128)
def get_stock_price(symbol):
    """Fetch real-time stock price using Alpha Vantage API."""
    try:
        url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if 'Global Quote' in data:
            return data['Global Quote']['05. price']
        return None
    except Exception as e:
        print(f"Error fetching stock price for {symbol}: {str(e)}")
        return None

def get_financial_news():
    """Fetch financial news using Alpha Vantage API."""
    url = f'https://www.alphavantage.co/query?function=NEWS_SENTIMENT&apikey={ALPHA_VANTAGE_API_KEY}'
    response = requests.get(url)
    data = response.json()
    if 'feed' in data:
        return data['feed'][:5]  # Return top 5 news articles
    return None

@app.route('/dashboard')
def index():
    """Render the dashboard."""
    return render_template('dashboard.html')

@socketio.on('request_update')
def handle_update_request():
    """Handle real-time updates for stock prices and news."""
    try:
        stock_symbols = ['AAPL', 'GOOGL', 'MSFT']
        stock_prices = {symbol: get_stock_price(symbol) for symbol in stock_symbols}
        news = get_financial_news()
        socketio.emit('update_data', {
            'status': 'success',
            'stock_prices': stock_prices, 
            'news': news
        })
    except Exception as e:
        socketio.emit('update_data', {
            'status': 'error',
            'message': str(e)
        })

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5001)
