# Passcode — Email OTP Authentication

A passwordless login demo using FastAPI, MySQL, SQLAlchemy, Gmail SMTP, and HTML/CSS/JavaScript.

## Features
- Email registration with OTP ownership verification
- Passwordless login for verified email addresses
- 6-digit OTP, 5-minute expiry, single use, and 3 wrong-attempt limit
- 60-second resend cooldown
- Hashed OTPs and server-side sessions; only session-token hashes are stored in MySQL
- Responsive login, registration, OTP and dashboard pages

## Requirements
- Python 3.11+
- MySQL Server 8+
- MySQL Workbench
- Gmail account with 2-Step Verification and a Google App Password

## Setup on Windows / VS Code
1. Open this folder in VS Code.
2. Open MySQL Workbench and run `schema.sql`.
3. In VS Code terminal, create and activate a virtual environment:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks activation, run commands with `.\.venv\Scripts\python.exe` instead.
4. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```
5. Copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
6. Edit `.env` and set `DB_USER`, `DB_PASSWORD`, a random `SECRET_KEY`, `SMTP_USERNAME`, and `SMTP_PASSWORD`. Use a Google App Password, not your normal Gmail password.
7. Start the server:
   ```powershell
   python -m uvicorn app.main:app --reload
   ```
8. Open http://127.0.0.1:8000

## Verify the database
Visit http://127.0.0.1:8000/api/health. Expected result:
`{"status":"ok","database":"connected"}`

## Test flow
1. Choose **Register Email** and submit your name and email.
2. Enter the code delivered to that email within five minutes.
3. Return to login, enter the verified email, request a login OTP, and verify it.
4. Confirm that the dashboard opens; test wrong and expired codes.
5. Inspect `users`, `email_otps`, and `sessions` in MySQL Workbench.

## Security / deployment notes
- Keep `.env` private; never commit credentials.
- For production use HTTPS and set `COOKIE_SECURE=true`.
- The in-memory rate limiter is intended for a single-process demo; use a shared limiter such as Redis for multi-worker deployment.
- Before public deployment, add CSRF protection for cookie-authenticated state-changing requests, operational monitoring, and a managed database with TLS.
- Never expose OTPs, SMTP credentials, database passwords, or session tokens in client-side code.
