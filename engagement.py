from flask import Blueprint, request, jsonify, render_template, session
from flask_login import login_required
import requests
import os
from functools import lru_cache, wraps
from datetime import datetime, timedelta
from dotenv import load_dotenv
import time
import json

load_dotenv()

engagement_bp = Blueprint('engagement_bp', __name__)

# Configuration
class Config:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    CACHE_TIMEOUT = 300  # Cache timeout in minutes
    REQUEST_TIMEOUT = 30  # Request timeout in seconds
    MAX_RETRIES = 3      # Maximum retry attempts
    RETRY_DELAY = 2      # Retry delay in seconds
    
    # Proxy settings (if needed)
    HTTP_PROXY = os.environ.get("HTTP_PROXY")
    HTTPS_PROXY = os.environ.get("HTTPS_PROXY")

# Check API key
if not Config.GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY environment variable not set")

# Proxy settings
proxies = {}
if Config.HTTP_PROXY:
    proxies['http'] = Config.HTTP_PROXY
if Config.HTTPS_PROXY:
    proxies['https'] = Config.HTTPS_PROXY

# Unified response format
def make_response(success=True, data=None, message=None, status_code=200):
    response = {
        "success": success,
        "timestamp": datetime.now().isoformat(),
        "data": data,
        "message": message
    }
    return jsonify(response), status_code

# Add retry decorator
def retry_on_failure(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        raise e
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

@retry_on_failure(max_retries=Config.MAX_RETRIES, delay=Config.RETRY_DELAY)
def get_gemini_response(prompt):
    """Get response from Google Gemini API"""
    if not Config.GEMINI_API_KEY:
        raise ValueError("System configuration error: Missing API key, please contact administrator")
        
    try:
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        url = f"{Config.GEMINI_API_URL}?key={Config.GEMINI_API_KEY}"
        
        # Send request
        try:
            print(f"Sending request to Gemini API...")  # Debug log
            response = requests.post(
                url, 
                json=payload, 
                headers=headers, 
                timeout=Config.REQUEST_TIMEOUT,
                proxies=proxies if proxies else None,
                verify=True  # SSL verification
            )
            print(f"Received response, status code: {response.status_code}")  # Debug log
            
            # Check response status code
            response.raise_for_status()
            
            # Check response Content-Type
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' not in content_type:
                print(f"Invalid Content-Type: {content_type}")  # Debug log
                raise ValueError(f"API returned non-JSON response: {content_type}")
            
            # Try to parse JSON
            try:
                result = response.json()
                print("Successfully parsed JSON response")  # Debug log
            except ValueError as e:
                print(f"JSON parsing error: {str(e)}")  # Debug log
                raise ValueError(f"Unable to parse API response as JSON: {str(e)}")
            
            # Validate response structure
            if not isinstance(result, dict):
                raise ValueError("Invalid API response format")
                
            if 'candidates' not in result or not result['candidates']:
                print(f"Response missing required fields: {result}")  # Debug log
                raise ValueError("API response missing required data fields")
                
            if not result['candidates'][0].get('content', {}).get('parts', []):
                raise ValueError("API response missing text content")
            
            response_text = result['candidates'][0]['content']['parts'][0]['text']
            print("Successfully retrieved response text")  # Debug log
            return response_text
            
        except requests.exceptions.Timeout:
            print("Request timeout")  # Debug log
            raise ConnectionError("API request timeout, please try again later")
        except requests.exceptions.RequestException as e:
            print(f"Request exception: {str(e)}")  # Debug log
            raise ConnectionError(f"API request failed: {str(e)}")
            
    except Exception as e:
        print(f"Gemini API error: {str(e)}")  # Debug log
        raise Exception(f"Error processing request: {str(e)}")

@engagement_bp.route('/')
@login_required
def index():
    """Render main page"""
    return render_template('engagement.html')

@engagement_bp.route('/profile/questions', methods=['GET'])
@login_required
def get_profile_questions():
    """Get user profile questions list"""
    try:
        questions = [
            "What is your age?",
            "What is your occupation?",
            "What is your monthly income?",
            "What are your monthly expenses?",
            "What is your asset status (e.g., savings, real estate)?",
            "What is your risk preference (conservative, moderate, or aggressive)?"
        ]
        return make_response(data={"questions": questions})
    except Exception as e:
        return make_response(success=False, message=str(e), status_code=500)

@engagement_bp.route('/profile', methods=['POST'])
@login_required
def analyze_profile():
    """Analyze user profile"""
    try:
        data = request.get_json()
        if not data:
            return make_response(
                success=False, 
                message="Request data is empty, please provide user information", 
                status_code=400
            )
            
        required_fields = ['age', 'occupation', 'monthly_income', 'monthly_expenses', 'assets', 'risk_preference']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return make_response(
                success=False, 
                message=f"Missing required information: {', '.join(missing_fields)}", 
                status_code=400
            )

        # Build detailed prompt
        prompt = """As a professional financial advisor, please provide a comprehensive user profile analysis and personalized financial advice based on the following information.
Please analyze from these aspects:

1. Basic Financial Status Analysis
2. Income and Expense Structure Assessment
3. Risk Tolerance Assessment
4. Investment Recommendations
5. Financial Goal Planning
6. Risk Warnings

User Information:
"""
        for field in required_fields:
            prompt += f"{field}: {data.get(field, '')}\n"
        
        try:
            analysis = get_gemini_response(prompt)
            if not analysis:
                return make_response(
                    success=False,
                    message="Unable to generate analysis, please try again later",
                    status_code=503
                )

            # Save user profile to session
            session['user_profile'] = {
                'analysis': analysis,
                'raw_data': data,
                'timestamp': datetime.now().isoformat()
            }

            return make_response(
                success=True,
                data={
                    "analysis": analysis,
                    "profile_data": data,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except (ConnectionError, ValueError) as e:
            print(f"Analysis generation error: {str(e)}")
            return make_response(
                success=False,
                message=f"Failed to generate analysis: {str(e)}",
                status_code=503
            )
        
    except Exception as e:
        print(f"Request processing error: {str(e)}")
        return make_response(
            success=False, 
            message=f"Error processing request: {str(e)}", 
            status_code=500
        )

@engagement_bp.route('/financial_advice', methods=['POST'])
@login_required
def financial_advice():
    """Generate personalized financial advice"""
    data = request.json
    prompt = "Generate personalized financial advice based on the following data:\n"
    prompt += f"Income: {data.get('income', '')}\n"
    prompt += f"Expenses: {data.get('expenses', '')}\n"
    prompt += f"Assets: {data.get('assets', '')}\n"
    prompt += f"Risk Profile: {data.get('risk_profile', '')}\n"
    
    ai_response = get_gemini_response(prompt)
    return make_response(data={"financial_advice": ai_response})

@engagement_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    """Handle chat requests"""
    data = request.get_json()
    if not data or 'message' not in data:
        return make_response(success=False, message="Missing message", status_code=400)
    
    message = data['message']
    conversation_history = data.get('conversation_history', '')
    
    response = get_gemini_response(conversation_history + "\nUser: " + message)
    return make_response(data={"response": response})

@engagement_bp.route('/custom_plan', methods=['POST'])
@login_required
def custom_plan():
    """Generate personalized financial plan"""
    data = request.json
    prompt = "Based on the following financial goals and current financial status, please provide a reasonable achievement plan and risk warnings:\n"
    prompt += f"Goal Type: {data.get('goal_type', '')}\n"
    prompt += f"Target Amount: {data.get('target_amount', '')}\n"
    prompt += f"Time Horizon: {data.get('time_horizon', '')}\n"
    
    current_finance = data.get("current_finance", {})
    if current_finance:
        prompt += ("Current Financial Status: "
                   f"Income {current_finance.get('income', '')}, "
                   f"Expenses {current_finance.get('expenses', '')}, "
                   f"Assets {current_finance.get('assets', '')}, "
                   f"Risk Profile {current_finance.get('risk_profile', '')}\n")
    
    ai_response = get_gemini_response(prompt)
    return make_response(data={"custom_plan": ai_response})

@engagement_bp.route('/simulation', methods=['POST'])
@login_required
def simulation():
    """Generate personalized investment simulation and advice based on user profile"""
    try:
        data = request.json
        # Validate basic parameters
        required_fields = ["initial_amount", "annual_rate", "years"]
        if not all(field in data for field in required_fields):
            return make_response(
                success=False,
                message="Missing required parameters: investment amount, expected return rate, and investment period",
                status_code=400
            )

        # Get parameters
        initial_amount = float(data["initial_amount"])
        annual_rate = float(data["annual_rate"])
        years = int(data["years"])

        # Get user profile
        user_profile = session.get('user_profile', {}).get('raw_data', {})
        if not user_profile:
            return make_response(
                success=False,
                message="Please complete personal profile analysis first",
                status_code=400
            )

        # Basic return calculation
        future_value = initial_amount * ((1 + annual_rate/100) ** years)
        monthly_investment = initial_amount / (12 * years) if years > 0 else 0

        # Generate investment advice prompt
        prompt = f"""As a professional investment advisor, please create a detailed investment plan based on the following user information and investment parameters:

User Profile Information:
- Age: {user_profile.get('age', 'Unknown')}
- Occupation: {user_profile.get('occupation', 'Unknown')}
- Monthly Income: {user_profile.get('monthly_income', 'Unknown')}
- Monthly Expenses: {user_profile.get('monthly_expenses', 'Unknown')}
- Asset Status: {user_profile.get('assets', 'Unknown')}
- Risk Preference: {user_profile.get('risk_preference', 'Unknown')}

Investment Parameters:
- Planned Investment Amount: ${initial_amount:,.2f}
- Expected Annual Return Rate: {annual_rate}%
- Investment Period: {years} years
- Monthly Average Investment: ${monthly_investment:,.2f}
- Expected Final Amount: ${future_value:,.2f}

Please provide the following detailed advice:
1. Investment Portfolio Allocation (based on user risk preference)
2. Specific Investment Product Recommendations and Ratios
3. Phased Investment Plan
4. Risk Control Measures
5. Regular Adjustment Suggestions
6. Market Volatility Response Strategies
7. Tax and Fee Considerations
8. Investment Goal Key Milestones
9. Emergency Fund Arrangements
10. Regular Review and Adjustment Plan

Please ensure the advice fully aligns with the user's risk tolerance and financial status."""

        try:
            # Get AI advice
            investment_advice = get_gemini_response(prompt)
            if not investment_advice:
                raise ValueError("Unable to generate investment advice")

            # Build complete investment plan
            investment_plan = {
                "initial_investment": initial_amount,
                "annual_return_rate": annual_rate,
                "investment_period": years,
                "monthly_investment": monthly_investment,
                "projected_final_amount": future_value,
                "user_profile_summary": {
                    "age": user_profile.get('age'),
                    "risk_preference": user_profile.get('risk_preference'),
                    "monthly_income": user_profile.get('monthly_income')
                },
                "detailed_plan": investment_advice
            }

            return make_response(data=investment_plan)

        except Exception as e:
            print(f"Error generating investment advice: {str(e)}")
            return make_response(
                success=False,
                message="Failed to generate investment advice, please try again later",
                status_code=503
            )

    except ValueError as e:
        return make_response(
            success=False,
            message="Parameter format error: Please ensure the amount, return rate, and period are valid numbers",
            status_code=400
        )
    except Exception as e:
        print(f"Request processing error: {str(e)}")
        return make_response(
            success=False,
            message="Error processing request, please try again later",
            status_code=500
        )

@engagement_bp.route('/update_advice', methods=['POST'])
@login_required
def update_advice():
    """Update financial advice"""
    data = request.json
    prompt = "Please update the financial advice based on the following latest information and real-time market data:\n"
    for key, value in data.items():
        prompt += f"{key}: {value}\n"
    
    ai_response = get_gemini_response(prompt)
    return make_response(data={"updated_advice": ai_response})
