from flask import Flask, request, jsonify, render_template
import requests
import os
from functools import lru_cache, wraps
from datetime import datetime, timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# 添加速率限制
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# 配置
class Config:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    CACHE_TIMEOUT = 300  # 缓存时间5分钟

# 统一的响应格式
def make_response(success=True, data=None, message=None, status_code=200):
    response = {
        "success": success,
        "timestamp": datetime.now().isoformat(),
        "data": data,
        "message": message
    }
    return jsonify(response), status_code

# 添加缓存装饰器
@lru_cache(maxsize=128)
def get_gemini_response(prompt):
    """调用 Google Gemini API 获取响应"""
    if not Config.GEMINI_API_KEY:
        app.logger.error("Missing Gemini API key in environment variables")
        return "系统配置错误：缺少 API 密钥，请联系管理员"
        
    try:
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }
        headers = {
            "Content-Type": "application/json"
        }
        
        url = f"{Config.GEMINI_API_URL}?key={Config.GEMINI_API_KEY}"
        response = requests.post(
            url, 
            json=payload, 
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        if 'candidates' in result and result['candidates']:
            return result['candidates'][0]['content']['parts'][0]['text']
        return "AI 未能生成有效回复"
        
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Gemini API 请求失败: {str(e)}")
        return "AI 服务暂时不可用，请稍后再试"
    except Exception as e:
        app.logger.error(f"处理请求时出错: {str(e)}")
        return "处理请求时发生错误"

@app.route('/profile/questions', methods=['GET'])
@limiter.limit("10/minute")
def get_profile_questions():
    """获取用户画像问题列表"""
    try:
        questions = [
            "请问您的年龄是多少？",
            "您的职业是？",
            "您的月收入是多少？",
            "您的月支出是多少？",
            "您的资产状况（例如存款、房产等）如何？",
            "您的风险偏好是保守、稳健还是激进？"
        ]
        return make_response(data={"questions": questions})
    except Exception as e:
        return make_response(success=False, message=str(e), status_code=500)

@app.route('/profile', methods=['POST'])
@limiter.limit("10/minute")
def analyze_profile():
    """分析用户画像"""
    try:
        data = request.get_json()
        app.logger.info(f"Received profile data: {data}")
        
        if not data:
            app.logger.error("Missing request data")
            return make_response(success=False, message="Missing request data", status_code=400)
            
        required_fields = ['age', 'occupation', 'monthly_income', 'monthly_expenses', 'assets', 'risk_preference']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            app.logger.error(f"Missing fields in request: {missing_fields}")
            return make_response(
                success=False, 
                message=f"Missing required fields: {', '.join(missing_fields)}", 
                status_code=400
            )

        prompt = "作为一个专业的理财顾问，请根据以下用户信息进行分析，建立用户画像，并提出个性化理财建议：\n"
        for field in required_fields:
            prompt += f"{field}: {data.get(field, '')}\n"
        
        app.logger.info(f"Sending prompt to Gemini: {prompt}")
        analysis = get_gemini_response(prompt)
        app.logger.info(f"Received analysis from Gemini: {analysis}")
        
        return make_response(data={"analysis": analysis})
        
    except Exception as e:
        app.logger.error(f"Error in analyze_profile: {str(e)}")
        return make_response(success=False, message=str(e), status_code=500)

@app.route('/financial_advice', methods=['POST'])
def financial_advice():
    """
    根据用户收支、资产和风险偏好信息，利用 AI 技术生成量身定制的理财建议
    """
    data = request.json
    prompt = "根据以下财务数据生成个性化的理财建议：\n"
    prompt += f"收入：{data.get('income', '')}\n"
    prompt += f"支出：{data.get('expenses', '')}\n"
    prompt += f"资产：{data.get('assets', '')}\n"
    prompt += f"风险偏好：{data.get('risk_profile', '')}\n"
    
    ai_response = get_gemini_response(prompt)
    return jsonify({"financial_advice": ai_response})

@app.route('/')
def index():
    """渲染主页面"""
    return render_template('engagement.html')

def get_financial_news():
    """Fetch financial news using Alpha Vantage API."""
    try:
        url = f'https://www.alphavantage.co/query?function=NEWS_SENTIMENT&apikey={Config.GEMINI_API_KEY}'
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'feed' in data:
            return data['feed'][:5]  # Return top 5 news articles
        return None
    except Exception as e:
        app.logger.error(f"获取新闻失败: {str(e)}")
        return None

# 添加错误处理装饰器
def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            app.logger.error(f"Error in {f.__name__}: {str(e)}")
            return make_response(success=False, message=str(e), status_code=500)
    return decorated_function

@app.route('/chat', methods=['POST'])
@handle_errors
@limiter.limit("20/minute")
def chat():
    """处理聊天请求"""
    data = request.get_json()
    if not data or 'message' not in data:
        return make_response(success=False, message="Missing message", status_code=400)
    
    message = data['message']
    conversation_history = data.get('conversation_history', '')
    
    response = get_gemini_response(conversation_history + "\n用户：" + message)
    return make_response(data={"response": response})

@app.route('/custom_plan', methods=['POST'])
def custom_plan():
    """
    用户可设定短期或长期财务目标，通过 AI 分析生成达成目标所需的理财方案和风险提示
    """
    data = request.json
    prompt = "用户设定了以下财务目标，请根据其当前财务状况提出合理的达成计划和风险提示：\n"
    prompt += f"目标类型：{data.get('goal_type', '')}\n"
    prompt += f"目标金额：{data.get('target_amount', '')}\n"
    prompt += f"时间范围：{data.get('time_horizon', '')}\n"
    
    current_finance = data.get("current_finance", {})
    if current_finance:
        prompt += ("当前财务状况："
                   f"收入 {current_finance.get('income', '')}, "
                   f"支出 {current_finance.get('expenses', '')}, "
                   f"资产 {current_finance.get('assets', '')}, "
                   f"风险偏好 {current_finance.get('risk_profile', '')}\n")
    
    ai_response = get_gemini_response(prompt)
    return jsonify({"custom_plan": ai_response})

@app.route('/simulation', methods=['POST'])
def simulation():
    """
    提供预算模拟、投资回报率计算等工具，帮助用户直观了解不同方案的效果，生成模拟预测报告
    """
    data = request.json
    try:
        initial_amount = float(data.get("initial_amount", 0))
        annual_rate = float(data.get("annual_rate", 0))
        years = int(data.get("years", 0))
    except ValueError:
        return jsonify({"error": "无效的数值参数"}), 400
    
    future_value = initial_amount * ((1 + annual_rate/100) ** years)
    prompt = (f"用户输入模拟参数：初始金额 {initial_amount}, 年利率 {annual_rate}%, 投资年限 {years}年。\n"
              f"请生成详细的模拟和预测报告，并说明预计未来金额为 {future_value:.2f}。")
    
    ai_response = get_gemini_response(prompt)
    return jsonify({
        "calculated_future_value": future_value,
        "simulation_report": ai_response
    })

@app.route('/update_advice', methods=['POST'])
def update_advice():
    """
    基于用户最新输入的信息和实时市场数据，动态调整并优化理财建议
    """
    data = request.json
    prompt = "请根据以下最新信息和实时市场数据更新理财建议：\n"
    for key, value in data.items():
        prompt += f"{key}: {value}\n"
    
    ai_response = get_gemini_response(prompt)
    return jsonify({"updated_advice": ai_response})

@app.errorhandler(429)
def ratelimit_handler(e):
    return make_response(success=False, message="请求过于频繁，请稍后再试", status_code=429)

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Unhandled exception: {str(e)}")
    return make_response(success=False, message="服务器内部错误", status_code=500)

if __name__ == '__main__':
    app.run(debug=os.environ.get("FLASK_DEBUG", False), port=5000)
