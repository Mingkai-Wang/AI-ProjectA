from flask import Blueprint, render_template, jsonify
from flask_login import login_required
import requests
import os
from datetime import datetime, timedelta
from functools import lru_cache
import json

dashboard_bp = Blueprint('dashboard_bp', __name__)

# Configuration
ALPHA_VANTAGE_API_KEY = os.environ.get('ALPHA_VANTAGE_API_KEY')
REQUEST_TIMEOUT = 10  # Request timeout in seconds

# Mock data (used when API is unavailable)
MOCK_DATA = {
    'stock_prices': {
        'AAPL': '180.25',
        'GOOGL': '140.50',
        'MSFT': '375.80'
    },
    'news': [
        {
            'title': 'Market Dynamics Analysis',
            'summary': 'Today\'s market remains stable with tech stocks showing slight gains.',
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'title': 'Economic Data Report',
            'summary': 'Latest economic data shows steady growth in the economy.',
            'time': (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'title': 'Industry Trend Analysis',
            'summary': 'Technology sector leads the market, with new energy sector showing strong performance.',
            'time': (datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
        }
    ]
}

@lru_cache(maxsize=128)
def get_stock_price(symbol):
    """Get real-time stock price"""
    if not ALPHA_VANTAGE_API_KEY:
        print(f"Warning: Alpha Vantage API key not set, using mock data")
        return MOCK_DATA['stock_prices'].get(symbol)
        
    try:
        url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}'
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        if 'Global Quote' in data:
            return data['Global Quote']['05. price']
        elif 'Note' in data:  # API rate limit warning
            print(f"API Rate Limit Warning: {data['Note']}")
            return MOCK_DATA['stock_prices'].get(symbol)
        else:
            print(f"Invalid API response format: {data}")
            return MOCK_DATA['stock_prices'].get(symbol)
            
    except requests.exceptions.Timeout:
        print(f"Timeout getting stock price for {symbol}")
        return MOCK_DATA['stock_prices'].get(symbol)
    except requests.exceptions.RequestException as e:
        print(f"Failed to get stock price for {symbol}: {str(e)}")
        return MOCK_DATA['stock_prices'].get(symbol)
    except Exception as e:
        print(f"Error processing stock data for {symbol}: {str(e)}")
        return MOCK_DATA['stock_prices'].get(symbol)

def get_financial_news():
    """Get financial news"""
    if not ALPHA_VANTAGE_API_KEY:
        print("Warning: Alpha Vantage API key not set, using mock data")
        return MOCK_DATA['news']
        
    try:
        url = f'https://www.alphavantage.co/query?function=NEWS_SENTIMENT&apikey={ALPHA_VANTAGE_API_KEY}'
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        if 'feed' in data:
            return data['feed'][:5]  # Return top 5 news
        elif 'Note' in data:  # API rate limit warning
            print(f"API Rate Limit Warning: {data['Note']}")
            return MOCK_DATA['news']
        else:
            print(f"Invalid API response format: {data}")
            return MOCK_DATA['news']
            
    except requests.exceptions.Timeout:
        print("Timeout getting news data")
        return MOCK_DATA['news']
    except requests.exceptions.RequestException as e:
        print(f"Failed to get news data: {str(e)}")
        return MOCK_DATA['news']
    except Exception as e:
        print(f"Error processing news data: {str(e)}")
        return MOCK_DATA['news']

@dashboard_bp.route('/')
@login_required
def index():
    """Render dashboard page"""
    try:
        return render_template('dashboard.html')
    except Exception as e:
        print(f"Failed to render dashboard page: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to load page, please refresh'
        }), 500

@dashboard_bp.route('/update_data')
@login_required
def update_data():
    """Handle real-time data update requests"""
    try:
        # Get stock data
        important_us_stock_tickers = [
            "AAPL", 
            "MSFT", 
            "AMZN", 
            "GOOG", 
            "META", 
            "TSLA", 
            "NVDA", 
        ]

        stock_symbols = important_us_stock_tickers
        stock_prices = {symbol: get_stock_price(symbol) for symbol in stock_symbols}
        
        # Get news data
        news = get_financial_news()
        
        # Validate data
        if not any(stock_prices.values()):
            raise ValueError("Failed to get valid stock data")
            
        if not news:
            raise ValueError("Failed to get valid news data")
        
        return jsonify({
            'success': True,
            'data': {
                'stock_prices': stock_prices,
                'news': news,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        print(f"Failed to update data: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Data update failed: {str(e)}',
            'data': MOCK_DATA  # Return mock data as fallback
        })
