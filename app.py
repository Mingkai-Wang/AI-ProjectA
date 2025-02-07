from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
from werkzeug.security import generate_password_hash, check_password_hash
from engagement import engagement_bp
from support import support_bp
from dashboard import dashboard_bp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create Flask application
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key')

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configure rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Register blueprints
app.register_blueprint(engagement_bp, url_prefix='/engagement')
app.register_blueprint(support_bp, url_prefix='/support')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

# Mock user database
users = {
    'admin@example.com': {
        'password': generate_password_hash('admin123'),
        'id': 1
    }
}

class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if email in users and check_password_hash(users[email]['password'], password):
            user = User(users[email]['id'])
            login_user(user)
            return redirect(url_for('index'))
        
        flash('Invalid email or password')
    return render_template('account.html')

@app.route('/index')
@login_required
def index():
    return render_template('index.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.errorhandler(429)
def ratelimit_handler(e):
    flash('Too many requests, please try again later')
    return redirect(url_for('login'))

@app.errorhandler(500)
def internal_error(e):
    flash('Internal server error, please try again later')
    return redirect(url_for('login'))

@app.errorhandler(404)
def not_found_error(e):
    flash('Page not found')
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Set application configuration
    app.config['RATELIMIT_HEADERS_ENABLED'] = True
    app.config['RATELIMIT_STORAGE_URL'] = 'memory://'
    app.config['RATELIMIT_STRATEGY'] = 'fixed-window'
    
    # Start application
    app.run(debug=True, port=5000)

'''
Default login credentials:
Email: admin@example.com
Password: admin123
'''