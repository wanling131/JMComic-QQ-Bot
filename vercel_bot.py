# vercel_bot.py
# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
import jmcomic
import threading
import os
import json
import hmac
import hashlib
import time
from datetime import datetime

app = Flask(__name__)

# QQ机器人配置
QQ_BOT_APP_ID = '102813016'
QQ_BOT_TOKEN = 'Przl2iicveVXOVEFO9MSYfLCcgWADLYQ'
QQ_BOT_QQ = '3889940060'

# 设置环境变量
os.environ["JM_DOWNLOAD_DIR"] = "/tmp/downloads"

# 下载状态存储
download_status = {}

class JMComicBot:
    def __init__(self):
        # 使用简化的配置
        self.option = jmcomic.create_option_by_file('assets/option/option_test_api.yml')
    
    def download_comic(self, comic_id, user_id):
        try:
            download_status[comic_id] = {
                "status": "downloading",
                "user_id": user_id,
                "start_time": datetime.now().isoformat()
            }
            
            print(f"开始下载本子 {comic_id}...")
            album, downloader = jmcomic.download_album(comic_id, self.option)
            
            download_status[comic_id] = {
                "status": "completed",
                "user_id": user_id,
                "start_time": download_status[comic_id]["start_time"],
                "end_time": datetime.now().isoformat(),
                "album_title": album.title,
                "author": album.author,
                "photo_count": len(album.photo_list) if hasattr(album, 'photo_list') else '未知'
            }
            
            return True, f"本子 {comic_id} 下载完成！标题: {album.title}"
            
        except Exception as e:
            print(f"下载本子 {comic_id} 时出错: {e}")
            import traceback
            traceback.print_exc()
            
            download_status[comic_id] = {
                "status": "failed",
                "user_id": user_id,
                "error": str(e),
                "time": datetime.now().isoformat()
            }
            return False, f"下载失败: {str(e)}"

bot = JMComicBot()

def verify_qq_signature(timestamp, nonce, body, signature):
    """验证QQ机器人签名"""
    try:
        string_to_sign = f"{timestamp}{nonce}{body}"
        calculated_signature = hmac.new(
            QQ_BOT_TOKEN.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return calculated_signature == signature
    except Exception as e:
        print(f"签名验证失败: {e}")
        return False

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "JMComic QQ Bot API 运行中"})

@app.route("/qq/callback", methods=["POST"])
def qq_callback():
    try:
        timestamp = request.headers.get('X-Signature-Timestamp', '')
        nonce = request.headers.get('X-Signature-Nonce', '')
        signature = request.headers.get('X-Signature-Ed25519', '')
        
        body = request.get_data(as_text=True)
        
        print(f"收到QQ回调: timestamp={timestamp}, nonce={nonce}")
        print(f"请求体: {body}")
        
        # if not verify_qq_signature(timestamp, nonce, body, signature):
        #     return jsonify({"code": 401, "message": "签名验证失败"}), 401
        
        data = request.json
        if not data:
            return jsonify({"code": 400, "message": "无效的JSON数据"}), 400
        
        if data.get("t") == "MESSAGE_CREATE":
            message_data = data.get("d", {})
            content = message_data.get("content", "")
            user_id = message_data.get("author", {}).get("id", "")
            channel_id = message_data.get("channel_id", "")
            
            print(f"收到消息: {content} (用户ID: {user_id})")
            
            if content.startswith("下载本子"):
                parts = content.split()
                if len(parts) >= 2:
                    comic_id = parts[1]
                    
                    def download_task():
                        success, message = bot.download_comic(comic_id, user_id)
                        print(f"下载结果: {message}")
                    
                    thread = threading.Thread(target=download_task)
                    thread.start()
                    
                    return jsonify({
                        "code": 0,
                        "message": f"开始下载本子 {comic_id}，请稍候..."
                    })
                else:
                    return jsonify({
                        "code": 1,
                        "message": "请提供本子ID，格式：下载本子 123456"
                    })
            
            elif content.startswith("查询状态"):
                parts = content.split()
                if len(parts) >= 2:
                    comic_id = parts[1]
                    if comic_id in download_status:
                        status = download_status[comic_id]
                        return jsonify({
                            "code": 0,
                            "message": f"本子 {comic_id} 状态: {status['status']}"
                        })
                    else:
                        return jsonify({
                            "code": 1,
                            "message": f"未找到本子 {comic_id} 的下载记录"
                        })
            
            elif content == "帮助" or content == "help":
                help_text = """
JMComic QQ机器人使用说明：
1. 下载本子：下载本子 123456
2. 查询状态：查询状态 123456
3. 查看帮助：帮助

机器人QQ号: 3889940060
                """
                return jsonify({
                    "code": 0,
                    "message": help_text
                })
        
        return jsonify({"code": 0, "message": "消息已接收"})
        
    except Exception as e:
        print(f"处理QQ消息时出错: {e}")
        return jsonify({"code": 1, "message": f"处理消息时出错: {str(e)}"}), 500

@app.route("/download", methods=["POST"])
def download_api():
    try:
        data = request.json
        comic_id = data.get("comic_id")
        user_id = data.get("user_id", "api_user")
        
        if not comic_id:
            return jsonify({"error": "缺少comic_id参数"}), 400
        
        def download_task():
            success, message = bot.download_comic(comic_id, user_id)
            print(f"API下载结果: {message}")
        
        thread = threading.Thread(target=download_task)
        thread.start()
        
        return jsonify({
            "status": "success",
            "message": f"开始下载本子 {comic_id}",
            "comic_id": comic_id
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/status/<comic_id>")
def get_status(comic_id):
    if comic_id in download_status:
        return jsonify(download_status[comic_id])
    else:
        return jsonify({"error": "未找到该本子的下载记录"}), 404

@app.route("/status")
def get_all_status():
    return jsonify(download_status)

if __name__ == "__main__":
    print("JMComic QQ Bot API 启动中...")
    print(f"机器人QQ号: {QQ_BOT_QQ}")
    print(f"AppID: {QQ_BOT_APP_ID}")
    print("API接口:")
    print("  POST /qq/callback - QQ机器人回调接口")
    print("  POST /download - 直接下载接口")
    print("  GET /status/<comic_id> - 查询下载状态")
    print("  GET /status - 查询所有状态")
    print("  GET / - 健康检查")
    print("\nQQ机器人命令:")
    print("  下载本子 123456 - 下载指定本子")
    print("  查询状态 123456 - 查询下载状态")
    print("  帮助 - 查看帮助信息")
    
    app.run(host="0.0.0.0", port=5000, debug=False)
