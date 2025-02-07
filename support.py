#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb  5 17:28:47 2025

@author: mingkaiwang
"""
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required
import json
import os
import signal
import psutil
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

support_bp = Blueprint('support_bp', __name__)

# Configure Google Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY environment variable not set")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    # Create Gemini model instance
    model = genai.GenerativeModel('gemini-pro')

# Configure file path
HISTORY_FILE = "question_history.json"

def load_history():
    """Load history from file"""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Failed to load history: {str(e)}")
        return []

def save_history(history):
    """Save history to file"""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Failed to save history: {str(e)}")
        return False

def release_port(port=5102):
    """Release specified port to prevent 'Address Already in Use' error"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and any("flask" in cmd for cmd in proc.info['cmdline']):
                    os.kill(proc.info['pid'], signal.SIGKILL)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"Failed to release port: {str(e)}")

# Release port before starting
release_port(5102)

# Load history
question_history = load_history()

# System prompt
SYSTEM_PROMPT = """You are a professional customer service assistant responsible for answering questions about company services. Please note:
1. Maintain a professional and friendly tone
2. Keep answers concise and clear
3. Be honest about uncertain information
4. For specific prices or special services, suggest contacting human customer service
5. Use polite language
6. Structure answers with clear focus points
7. Ask for clarification if user questions are unclear

Company Information:
- Working Hours: 9 AM to 6 PM on weekdays
- Address: Central Business District
- Contact: Phone 400-888-8888, Email support@example.com
- Payment Methods: Bank Transfer, PayPal, and Credit Cards
"""

@support_bp.route("/")
@login_required
def index():
    """Render chat bot interface"""
    return render_template("support.html")

@support_bp.route("/get_history")
@login_required
def get_history():
    """Get chat history"""
    try:
        history = load_history()
        return jsonify({"success": True, "history": history})
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to load history: {str(e)}"
        }), 500

@support_bp.route("/chat", methods=["POST"])
@login_required
def chat():
    """Handle user messages and provide responses using Gemini API"""
    try:
        if not request.is_json:
            return jsonify({
                "success": False,
                "error": "Invalid request format, JSON required"
            }), 400

        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({
                "success": False,
                "error": "Message cannot be empty"
            }), 400

        user_message = data['message'].strip()
        if not user_message:
            return jsonify({
                "success": False,
                "error": "Message cannot be empty"
            }), 400

        if not GEMINI_API_KEY:
            return jsonify({
                "success": False,
                "error": "System configuration error: API key not set"
            }), 500

        try:
            # Create chat context
            chat = model.start_chat(history=[])
            # Send system prompt and user message
            response = chat.send_message(f"{SYSTEM_PROMPT}\n\nUser Question: {user_message}")
            bot_reply = response.text

            # Record question
            new_history_item = {
                "question": user_message,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            question_history.append(new_history_item)
            save_history(question_history)

            return jsonify({
                "success": True,
                "response": bot_reply,
                "history": question_history
            })

        except Exception as e:
            print(f"Gemini API Error: {str(e)}")
            return jsonify({
                "success": False,
                "error": f"AI response generation failed: {str(e)}"
            }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Request processing error: {str(e)}"
        }), 500

if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY environment variable not set")
        exit(1)
    current_app.run(debug=True, port=5102)

