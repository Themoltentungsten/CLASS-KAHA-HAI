# 🤖 Class Kaha Hai – Telegram Bot  

![Bot Logo](ClassKahaHai.png)

A smart **Telegram bot** built for **CVRGU Group-7 (Sem 5)** students to easily check their class schedule, get reminders, and stay updated with announcements.  
Deployed on **Render** for 24/7 availability.  

---

## ✨ Features
- 📅 **Timetable Lookup**  
  - `/today` – view today’s full schedule  
  - `/tomorrow` – check tomorrow’s classes  
  - `/week` – see the entire week in one view  

- ⏰ **Reminders**  
  - `/subscribe` – get notified **10 minutes before each class**  

- 🔎 **Quick Info**  
  - `Where is the class?` – tells you the current/next class with room & faculty  
  - `Who is the developer?` – credits & info  

- 📢 **Admin Announcements**  
  - `/announce <message>` – broadcast updates to all registered chats (admin only)  

- 🕒 Handles special cases:  
  - Before 9:30 → shows first class (not "closed")  
  - Lunch (13:30–14:30) → shows lunch + next class  
  - After 17:30 → shows next day’s class  

---

## 🛠 Tech Stack
- **Language:** Python 3.10+  
- **Framework:** [python-telegram-bot 21.x](https://docs.python-telegram-bot.org/)  
- **Server:** aiohttp (async webhook server)  
- **Hosting:** [Render](https://render.com) (free tier with uptime pinger)  
- **Scheduler:** PTB JobQueue for reminders  
- **Monitoring:** UptimeRobot / Cron-job.org  

---

## 🚀 Getting Started

### 1. Clone the Repo
```bash
git clone https://github.com/<your-username>/Class-Kaha-Hai.git
cd Class-Kaha-Hai
```

### 2. Install Requirements
```bash
pip install -r requirements.txt
```

### 3. Set Environment Variables
Create a `.env` file or use Render dashboard:  
```env
TELEGRAM_BOT_TOKEN=your_botfather_token_here
WEBHOOK_URL=https://<your-service>.onrender.com/webhook
```

### 4. Run Locally
For quick test with polling:
```bash
python main.py
```

For production webhook (Render):
```bash
python webhook_main.py
```

---

## 📸 Demo
- Start chat with the bot: [@YourBotUsername](https://t.me/YourBotUsername)  
- Example commands:  

```
/today
/next
/subscribe
```

---

## 👨‍💻 Developer
- Built by **Yash Kumar Raut (@Moltentungsten)**  
- CVRGU Group-7 timetable automation project  

---

## 📜 License
MIT License – free to use, modify, and share.  
