from pathlib import Path
from fastapi import FastAPI, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.database import get_db
from app import auth
from app.schemas import RegisterRequest, EmailRequest, VerifyOtpRequest
from app.errors import AppError, EmailDeliveryError
from config import SESSION_COOKIE_NAME, get_settings

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Passcode Email OTP Authentication", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(ROOT / "templates"))

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
    return response

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    body = {"success": False, "code": exc.code, "message": exc.message}
    headers = {}
    if exc.retry_after is not None:
        body["retry_after"] = exc.retry_after
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(body, status_code=exc.status_code, headers=headers)

@app.exception_handler(EmailDeliveryError)
async def email_error_handler(request: Request, exc: EmailDeliveryError):
    return JSONResponse({"success": False, "code": "email_failed", "message": "We could not send the email. Check the email configuration and try again."}, status_code=503)

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    user = auth.get_current_user(db, request.cookies.get(SESSION_COOKIE_NAME))
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Session = Depends(get_db)):
    user = auth.get_current_user(db, request.cookies.get(SESSION_COOKIE_NAME))
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="register.html", context={})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = auth.get_current_user(db, request.cookies.get(SESSION_COOKIE_NAME))
    if not user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"user": user})

@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except SQLAlchemyError:
        return JSONResponse({"status": "error", "database": "unavailable", "code": "database_unavailable"}, status_code=503)

@app.post("/api/auth/register", status_code=201)
def api_register(payload: RegisterRequest, db: Session = Depends(get_db)):
    return auth.register(db, payload.name, payload.email)

@app.post("/api/auth/register/send-otp")
def api_register_send(payload: EmailRequest, db: Session = Depends(get_db)):
    return auth.send_registration_otp(db, payload.email)

@app.post("/api/auth/register/verify-otp")
def api_register_verify(payload: VerifyOtpRequest, db: Session = Depends(get_db)):
    return auth.verify_registration_otp(db, payload.email, payload.otp)

@app.post("/api/auth/login/send-otp")
def api_login_send(payload: EmailRequest, db: Session = Depends(get_db)):
    return auth.send_login_otp(db, payload.email)

@app.post("/api/auth/login/verify-otp")
def api_login_verify(payload: VerifyOtpRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    result = auth.verify_login_otp(db, payload.email, payload.otp, request.client.host if request.client else None, request.headers.get("user-agent"))
    token = result.pop("session_token")
    settings = get_settings()
    response.set_cookie(SESSION_COOKIE_NAME, token, httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=settings.session_hours * 3600, path="/")
    return result

@app.get("/api/auth/me")
def api_me(request: Request, db: Session = Depends(get_db)):
    user = auth.get_current_user(db, request.cookies.get(SESSION_COOKIE_NAME))
    if not user:
        raise AppError(401, "not_authenticated", "Please log in to continue.")
    return {"success": True, "user": {"name": user.name, "email": user.email, "last_login": user.last_login.isoformat() + "Z" if user.last_login else None}}

@app.post("/api/auth/logout")
def api_logout(request: Request, response: Response, db: Session = Depends(get_db)):
    auth.logout(db, request.cookies.get(SESSION_COOKIE_NAME))
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", httponly=True, samesite="lax")
    return {"success": True, "message": "Logged out successfully.", "redirect": "/"}

@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse({"success": False, "code": "database_unavailable", "message": "The database is temporarily unavailable. Please try again."}, status_code=503)
