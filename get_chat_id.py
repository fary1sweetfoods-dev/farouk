import requests

TOKEN = "8813285194:AAFcJSG9xBv46cY6clalUmQRCZexddmrSE"
url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset=-5"

res = requests.get(url).json()

if res.get("result"):
    for item in res["result"]:
        # Extract from message, edited_message, or my_chat_member
        msg = item.get("message") or item.get("edited_message") or item.get("my_chat_member")
        if msg and "chat" in msg:
            chat = msg["chat"]
            print(f"🎯 Group Title: {chat.get('title')}")
            print(f"👉 REAL CHAT ID: {chat.get('id')}")
            print("---------------------------------------")
else:
    print("❌ Still no response. Make sure you sent '/id @mkhavisobot' in the group!")