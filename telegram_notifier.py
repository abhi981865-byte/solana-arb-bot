#!/usr/bin/env python3
"""
Enhanced Telegram Notifier with detailed trade alerts
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional

class TelegramNotifier:
    """Send professional alerts to Telegram"""
    
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)
        self.api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    def send(self, message: str, parse_mode: str = "HTML"):
        """Send message to Telegram"""
        if not self.enabled:
            return False
        
        try:
            requests.post(
                self.api_url,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": parse_mode
                },
                timeout=5
            )
            return True
        except Exception as e:
            print(f"⚠️  Telegram send failed: {e}")
            return False
    
    def alert_startup(self, balance: float):
        """Bot startup alert"""
        msg = (
            f"🚀 <b>Bot Started</b>\n\n"
            f"💰 Balance: ${balance:.2f}\n"
            f"📊 Status: Paper Trading\n"
            f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"<i>Updates every 30 seconds on dashboard</i>"
        )
        self.send(msg)
    
    def alert_trade_executed(self, pair: str, profit: float, status: str, spread: float):
        """Trade execution alert"""
        emoji = "✅" if status == "filled" else "⚠️" if status == "partial_fill" else "❌"
        color = "✅" if profit > 0 else "❌"
        
        msg = (
            f"{emoji} <b>Trade Executed</b>\n\n"
            f"<b>Pair:</b> {pair}\n"
            f"<b>Spread:</b> {spread:.3f}%\n"
            f"<b>Profit:</b> {color} ${profit:+.4f}\n"
            f"<b>Status:</b> <code>{status}</code>"
        )
        self.send(msg)
    
    def alert_daily_summary(self, summary: Dict):
        """Daily performance summary"""
        msg = (
            f"📊 <b>Daily Summary</b>\n\n"
            f"💰 Balance: ${summary['balance_usd']:.2f}\n"
            f"📈 ROI: {summary['roi_pct']:+.3f}%\n"
            f"🎯 Trades: {summary['total_trades']}\n"
            f"✅ Success Rate: {summary['fill_success_rate_pct']:.1f}%\n"
            f"🔴 Failed: {summary['failed_trades']}\n"
            f"⚠️  Circuit Breaker: {'TRIPPED' if summary['circuit_breaker_tripped'] else 'OK'}"
        )
        self.send(msg)
    
    def alert_shutdown(self, summary: Dict, uptime: str):
        """Bot shutdown alert"""
        msg = (
            f"🛑 <b>Bot Shutdown</b>\n\n"
            f"💰 Final Balance: ${summary['balance_usd']:.2f}\n"
            f"📈 Final ROI: {summary['roi_pct']:+.3f}%\n"
            f"⏱️  Uptime: {uptime}\n"
            f"🎯 Total Trades: {summary['total_trades']}\n\n"
            f"<i>Restart to resume trading</i>"
        )
        self.send(msg)
    
    def alert_circuit_breaker(self):
        """Circuit breaker triggered"""
        msg = (
            f"🔴 <b>Circuit Breaker Triggered!</b>\n\n"
            f"3 consecutive losses detected.\n"
            f"Bot paused to protect capital.\n\n"
            f"<i>Will resume after manual reset</i>"
        )
        self.send(msg)

