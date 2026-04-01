"""
Servboard 2.0 — FastAPI Backend
Provides: JWT Auth, per-user SQLite data, metrics, secure command execution.
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, List
import psutil, os, subprocess, uvicorn, platform, time


# ─── Config ───────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production-use-random-string")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
SCRIPTS_ROOT = os.environ.get("SCRIPTS_ROOT", "/home/user/main")
DB_URL = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'users.db')}"

# ─── Database Setup ───────────────────────────────────────────────────────────
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    pages = relationship("Page", back_populates="owner", cascade="all, delete")
    prefs = relationship("Preference", back_populates="owner", uselist=False, cascade="all, delete")

class Page(Base):
    __tablename__ = "pages"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    icon = Column(String, default="grid_view")
    order = Column(Integer, default=0)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="pages")
    buttons = relationship("Button", back_populates="page", cascade="all, delete")

class Button(Base):
    __tablename__ = "buttons"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    command = Column(Text, nullable=False)
    icon = Column(String, default="play_arrow")
    color = Column(String, default="#37474f")
    order = Column(Integer, default=0)
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    page = relationship("Page", back_populates="buttons")

class Preference(Base):
    __tablename__ = "preferences"
    id = Column(Integer, primary_key=True, index=True)
    theme = Column(String, default="dark")
    poll_interval = Column(Integer, default=5)
    default_page_id = Column(Integer, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    owner = relationship("User", back_populates="prefs")

Base.metadata.create_all(bind=engine)

# ─── Auth Helpers ─────────────────────────────────────────────────────────────
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def verify_password(plain, hashed): return pwd_ctx.verify(plain, hashed)
def hash_password(password): return pwd_ctx.hash(password)

def create_token(data: dict):
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({**data, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    cred_exc = HTTPException(status_code=401, detail="Invalid credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None: raise cred_exc
    except JWTError: raise cred_exc
    user = db.query(User).filter(User.username == username).first()
    if user is None: raise cred_exc
    return user

# ─── Pydantic Schemas ─────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    password: str

class CommandRequest(BaseModel):
    command: str
    sudo_password: str

class PageCreate(BaseModel):
    name: str
    icon: Optional[str] = "grid_view"
    order: Optional[int] = 0

class PageUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    order: Optional[int] = None

class ButtonCreate(BaseModel):
    name: str
    command: str
    icon: Optional[str] = "play_arrow"
    color: Optional[str] = "#37474f"
    order: Optional[int] = 0

class ButtonUpdate(BaseModel):
    name: Optional[str] = None
    command: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    order: Optional[int] = None

class PrefsUpdate(BaseModel):
    theme: Optional[str] = None
    poll_interval: Optional[int] = None
    default_page_id: Optional[int] = None

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="Servboard API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Auth Routes ──────────────────────────────────────────────────────────────
@app.post("/api/auth/register", status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(400, "Username already exists")
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    user = User(username=req.username, hashed_password=hash_password(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    # Create default preferences
    db.add(Preference(owner_id=user.id))
    db.commit()
    return {"message": f"User '{req.username}' created"}

@app.post("/api/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Incorrect username or password")
    token = create_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/api/users/me")
def get_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "created_at": user.created_at}

# ─── System Routes ─────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": time.time()}

@app.get("/api/system")
def system_info(user: User = Depends(get_current_user)):
    boot_time = psutil.boot_time()
    uptime_secs = int(time.time() - boot_time)
    hours, rem = divmod(uptime_secs, 3600)
    minutes, seconds = divmod(rem, 60)
    return {
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "uptime": f"{hours}h {minutes}m {seconds}s",
        "cpu_count": psutil.cpu_count()
    }

@app.get("/api/metrics")
def get_metrics(user: User = Depends(get_current_user)):
    cpu_per_core = psutil.cpu_percent(percpu=True)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    gpu = _get_gpu()
    procs = sorted(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
                   key=lambda p: p.info['cpu_percent'], reverse=True)[:8]
    return {
        "cpu": psutil.cpu_percent(),
        "cpu_per_core": cpu_per_core,
        "ram": {"percent": ram.percent, "used_gb": round(ram.used / 1e9, 2), "total_gb": round(ram.total / 1e9, 2)},
        "disk": {"percent": disk.percent, "used_gb": round(disk.used / 1e9, 2), "total_gb": round(disk.total / 1e9, 2)},
        "gpu": gpu,
        "processes": [{"pid": p.info["pid"], "name": p.info["name"], "cpu": p.info["cpu_percent"], "mem": round(p.info["memory_percent"], 1)} for p in procs]
    }

def _get_gpu():
    # NVIDIA
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"], text=True, timeout=3)
        parts = [p.strip() for p in out.strip().split(",")]
        return [{"type": "NVIDIA", "name": parts[0], "usage": int(parts[1]), "vram_used": int(parts[2]), "vram_total": int(parts[3])}]
    except: pass
    # Intel
    try:
        usage = int(open("/sys/class/drm/card0/device/gpu_busy_percent").read().strip())
        return [{"type": "Intel", "name": "Integrated Graphics", "usage": usage}]
    except: pass
    # AMD
    try:
        out = subprocess.check_output(["rocm-smi", "--showuse"], text=True, timeout=3)
        import re; match = re.search(r'(\d+)%', out)
        if match: return [{"type": "AMD", "name": "AMD Radeon", "usage": int(match.group(1))}]
    except: pass
    return []

@app.post("/api/execute")
def execute_command(req: CommandRequest, user: User = Depends(get_current_user)):
    # Verify sudo password first
    try:
        check = subprocess.run(
            ["sudo", "-S", "-k", "true"],
            input=req.sudo_password + "\n",
            capture_output=True, text=True, timeout=5
        )
        if check.returncode != 0:
            raise HTTPException(status_code=403, detail="Invalid sudo password")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Sudo verification timed out")

    # Run the actual command
    try:
        result = subprocess.run(
            req.command, shell=True,
            capture_output=True, text=True, timeout=30
        )
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Command timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scripts")
def get_scripts(user: User = Depends(get_current_user)):
    scripts = {}
    if not os.path.exists(SCRIPTS_ROOT):
        return scripts
    for root, _, files in os.walk(SCRIPTS_ROOT):
        for f in files:
            if f.endswith(".sh"):
                cat = os.path.relpath(root, SCRIPTS_ROOT).upper() if root != SCRIPTS_ROOT else "GENERAL"
                if cat not in scripts: scripts[cat] = []
                scripts[cat].append({
                    "name": f.replace(".sh", "").replace("_", " ").upper(),
                    "path": os.path.join(root, f)
                })
    return scripts

# ─── Pages Routes ─────────────────────────────────────────────────────────────
@app.get("/api/pages")
def list_pages(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pages = db.query(Page).filter(Page.owner_id == user.id).order_by(Page.order).all()
    return [{"id": p.id, "name": p.name, "icon": p.icon, "order": p.order} for p in pages]

@app.post("/api/pages", status_code=201)
def create_page(req: PageCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page = Page(name=req.name, icon=req.icon, order=req.order, owner_id=user.id)
    db.add(page); db.commit(); db.refresh(page)
    return {"id": page.id, "name": page.name, "icon": page.icon, "order": page.order}

@app.put("/api/pages/{page_id}")
def update_page(page_id: int, req: PageUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page = db.query(Page).filter(Page.id == page_id, Page.owner_id == user.id).first()
    if not page: raise HTTPException(404, "Page not found")
    if req.name is not None: page.name = req.name
    if req.icon is not None: page.icon = req.icon
    if req.order is not None: page.order = req.order
    db.commit()
    return {"id": page.id, "name": page.name}

@app.delete("/api/pages/{page_id}", status_code=204)
def delete_page(page_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page = db.query(Page).filter(Page.id == page_id, Page.owner_id == user.id).first()
    if not page: raise HTTPException(404, "Page not found")
    db.delete(page); db.commit()

# ─── Buttons Routes ───────────────────────────────────────────────────────────
@app.get("/api/pages/{page_id}/buttons")
def list_buttons(page_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page = db.query(Page).filter(Page.id == page_id, Page.owner_id == user.id).first()
    if not page: raise HTTPException(404, "Page not found")
    return [{"id": b.id, "name": b.name, "command": b.command, "icon": b.icon, "color": b.color, "order": b.order} for b in sorted(page.buttons, key=lambda x: x.order)]

@app.post("/api/pages/{page_id}/buttons", status_code=201)
def create_button(page_id: int, req: ButtonCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page = db.query(Page).filter(Page.id == page_id, Page.owner_id == user.id).first()
    if not page: raise HTTPException(404, "Page not found")
    btn = Button(name=req.name, command=req.command, icon=req.icon, color=req.color, order=req.order, page_id=page_id)
    db.add(btn); db.commit(); db.refresh(btn)
    return {"id": btn.id, "name": btn.name}

@app.put("/api/buttons/{button_id}")
def update_button(button_id: int, req: ButtonUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    btn = db.query(Button).join(Page).filter(Button.id == button_id, Page.owner_id == user.id).first()
    if not btn: raise HTTPException(404, "Button not found")
    for field, val in req.dict(exclude_none=True).items():
        setattr(btn, field, val)
    db.commit()
    return {"id": btn.id, "name": btn.name}

@app.delete("/api/buttons/{button_id}", status_code=204)
def delete_button(button_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    btn = db.query(Button).join(Page).filter(Button.id == button_id, Page.owner_id == user.id).first()
    if not btn: raise HTTPException(404, "Button not found")
    db.delete(btn); db.commit()

# ─── Preferences ──────────────────────────────────────────────────────────────
@app.get("/api/prefs")
def get_prefs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prefs = db.query(Preference).filter(Preference.owner_id == user.id).first()
    if not prefs:
        prefs = Preference(owner_id=user.id)
        db.add(prefs); db.commit(); db.refresh(prefs)
    return {"theme": prefs.theme, "poll_interval": prefs.poll_interval, "default_page_id": prefs.default_page_id}

@app.put("/api/prefs")
def update_prefs(req: PrefsUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prefs = db.query(Preference).filter(Preference.owner_id == user.id).first()
    if not prefs:
        prefs = Preference(owner_id=user.id)
        db.add(prefs)
    for field, val in req.dict(exclude_none=True).items():
        setattr(prefs, field, val)
    db.commit()
    return {"message": "Preferences updated"}

# ─── Mount Flet App ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("FLET_SERVER_PORT", 3000))
    uvicorn.run(app, host="0.0.0.0", port=port)

