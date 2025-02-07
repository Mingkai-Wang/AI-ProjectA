#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb  5 17:28:47 2025

@author: mingkaiwang
"""
from flask import Flask, render_template, request, jsonify
import json
import os
import signal
import psutil
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = Flask(__name__)

# 配置Google Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

# 创建Gemini模型实例
model = genai.GenerativeModel('gemini-pro')

# 配置文件路径
HISTORY_FILE = "question_history.json"

def load_history():
    """从文件加载历史记录"""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"加载历史记录失败: {str(e)}")
    return []

def save_history(history):
    """保存历史记录到文件"""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存历史记录失败: {str(e)}")

def release_port(port=5102):
    """释放指定端口，防止'Address Already in Use'错误"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and any("flask" in cmd for cmd in proc.info['cmdline']):
                    os.kill(proc.info['pid'], signal.SIGKILL)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"释放端口失败: {str(e)}")

# 在启动前释放端口
release_port(5102)

# 加载历史记录
question_history = load_history()

# 系统提示词
SYSTEM_PROMPT = """你是一个专业的客服助手，负责回答用户关于公司服务的问题。请注意：
1. 保持专业、友好的语气
2. 回答要简洁明了
3. 如果不确定的信息，要诚实告知
4. 涉及具体价格或特殊服务时，建议用户联系人工客服
5. 使用礼貌用语，如"您"而不是"你"
6. 回答要有条理，重点突出
7. 如果用户问题不清楚，可以请求澄清

公司基本信息：
- 工作时间：每个工作日上午9点到下午6点
- 地址：中央商务区
- 联系方式：电话 400-888-8888，邮箱 support@example.com
- 支持多种支付方式：银行转账、支付宝和微信支付
"""

@app.route("/")
def index():
    """渲染聊天机器人界面"""
    return render_template("support.html")

@app.route("/get_history")
def get_history():
    """获取历史记录"""
    return jsonify({"history": question_history})

@app.route("/chat", methods=["POST"])
def chat():
    """处理用户消息并使用Gemini API提供回复"""
    try:
        user_message = request.json.get("message", "").strip()
        if not user_message:
            return jsonify({"error": "消息不能为空"}), 400

        try:
            # 创建对话上下文
            chat = model.start_chat(history=[])
            # 发送系统提示词和用户消息
            response = chat.send_message(f"{SYSTEM_PROMPT}\n\n用户问题：{user_message}")
            bot_reply = response.text

            # 记录问题
            question_history.append({
                "question": user_message,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_history(question_history)

            return jsonify({
                "response": bot_reply,
                "history": question_history
            })

        except Exception as e:
            print(f"Gemini API 错误: {str(e)}")
            return jsonify({
                "error": "抱歉，系统暂时无法处理您的请求，请稍后再试。"
            }), 500

    except Exception as e:
        return jsonify({
            "error": f"处理请求时发生错误: {str(e)}"
        }), 500

if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("错误：未设置GEMINI_API_KEY环境变量")
        exit(1)
    app.run(debug=True, port=5102)

