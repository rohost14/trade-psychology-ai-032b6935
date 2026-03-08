# TradeMentor AI

TradeMentor AI is an intelligent behavioral analysis platform designed to help traders improve their performance by analyzing their trading psychology. It connects directly with your brokerage account to monitor trades in real-time, detect emotional trading patterns, and provides AI-driven insights to help you maintain discipline.

## Problem Solved
Most traders fail not because of a lack of technical knowledge, but due to psychological barriers. Emotional decisions lead to:
- Revenge Trading: Trying to win back losses immediately with high risk.
- Overtrading: Taking low-quality setups out of boredom or compulsion.
- Tilt: emotional frustration leading to irrational decisions.
- Gambler's Fallacy: Believing a win is "due" after a series of losses.
- Loss Aversion: Holding losing trades for too long hoping they will turn around.

TradeMentor AI acts as a real-time risk guardian and behavioral analyst, offering objective feedback and automated risk management when you need it most.

## Key Features
- Real-time Broker Integration: Seamlessly connects with Zerodha (Kite Connect) to fetch orders and positions instantly.
- Behavioral Pattern Detection: Algorithms analyze your trading frequency, P&L fluctuations, and timing to flag risky behaviors.
- AI Behavioral Insights: Uses LLMs (via OpenRouter/Anthropic) to provide personalized analysis of your trading behavior and psychology.
- Instant Alerts: Sends critical risk alerts and daily summaries via WhatsApp (Twilio) to keep you accountable.
- Performance Dashboard: A modern, responsive React frontend to visualize your trading metrics and psychological state.

## Tech Stack
- Frontend: React (Vite), Tailwind CSS, TypeScript
- Backend: FastAPI (Python)
- Database: PostgreSQL (Supabase)

## Infrastructure
- Database: Supabase Postgres
- LLM: OpenRouter
- Broker API: Kite Connect
