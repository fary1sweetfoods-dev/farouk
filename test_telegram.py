from telegram_notifier import send_telegram_alert

if __name__ == "__main__":
    print("🚀 Sending test message via crt_bot...")
    success = send_telegram_alert("🟢 **crt_bot Online!** Connection verified successfully.")

    if success:
        print("✅ Test message delivered successfully! Check your Telegram DM.")
    else:
        print("❌ Failed to deliver test message. Check your console logs.")