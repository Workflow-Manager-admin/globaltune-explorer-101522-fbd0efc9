"""
MuseMap Backend: FastAPI application for personalized music discovery, playlist generation,
user/context management, and trending track exploration with SQLite DB.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, Field, EmailStr
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from passlib.context import CryptContext
import os
import sqlite3

# ------------ App/DB Initialization ------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "../../../musemap.sqlite3")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# ------------ ORM Models ------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(128), nullable=False)
    language_pref = Column(String(5), default="en")
    theme = Column(String(10), default="light")  # "dark" or "light"
    created_at = Column(DateTime, default=datetime.utcnow)

    playlists = relationship("Playlist", back_populates="owner")


playlist_track_association = Table(
    'playlist_track', Base.metadata,
    Column('playlist_id', Integer, ForeignKey('playlists.id')),
    Column('track_id', Integer, ForeignKey('tracks.id'))
)

class Playlist(Base):
    __tablename__ = "playlists"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    context_activity = Column(String(50))
    context_time = Column(String(20))
    context_language = Column(String(10))
    context_location = Column(String(50))  # city/country
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="playlists")
    tracks = relationship("Track", secondary=playlist_track_association, back_populates="playlists")

class Track(Base):
    __tablename__ = "tracks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100))
    artist = Column(String(100))
    album = Column(String(100), nullable=True)
    duration = Column(Integer, nullable=True)
    language = Column(String(10))
    country = Column(String(10))  # Country code (e.g., "US")
    trending_score = Column(Integer, default=0)
    external_url = Column(String(255), nullable=True)

    playlists = relationship("Playlist", secondary=playlist_track_association, back_populates="tracks")


# ------------ Security ------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------ Pydantic Schemas ------------
# User schemas
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    email: EmailStr
    language_pref: Optional[str] = "en"
    theme: Optional[str] = "light"

class UserLogin(BaseModel):
    username: str
    password: str

class UserProfileOut(BaseModel):
    id: int
    username: str
    email: str
    language_pref: str
    theme: str
    created_at: datetime

    class Config:
        from_attributes = True

# Track schemas
class TrackOut(BaseModel):
    id: int
    title: str
    artist: str
    album: Optional[str] = None
    duration: Optional[int] = None
    language: str
    country: str
    trending_score: int
    external_url: Optional[str]

    class Config:
        from_attributes = True

# Playlist schemas
class PlaylistCreate(BaseModel):
    name: str = Field(..., min_length=1)
    context_activity: Optional[str]
    context_time: Optional[str]
    context_language: Optional[str]
    context_location: Optional[str]

class PlaylistOut(BaseModel):
    id: int
    name: str
    context_activity: Optional[str]
    context_time: Optional[str]
    context_language: Optional[str]
    context_location: Optional[str]
    created_at: datetime
    tracks: List[TrackOut]

    class Config:
        from_attributes = True

class TrendingTrackOut(BaseModel):
    track: TrackOut
    location: str

# ------------- OpenAPI Metadata -------------
openapi_tags = [
    {"name": "User", "description": "Operations related to user registration, login, and profiles."},
    {"name": "Music", "description": "Music discovery, trending tracks, playlist recommendations."},
    {"name": "Playlist", "description": "Creating and managing user playlists."},
    {"name": "Health", "description": "Health check and status endpoints."}
]

# ------------ FastAPI Initialization ------------
app = FastAPI(
    title="MuseMap Backend API",
    description="Backend for personalized music discovery, playlist generation, user/context management, and trending tracks.",
    version="1.0.0",
    openapi_tags=openapi_tags
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------ Utility Functions ------------
def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def fake_generate_playlist(context, db: Session):
    """
    Simulates playlist generation based on context selectors.
    In real app, apply recommendation logic. Now just select random tracks from context filter.
    """
    query = db.query(Track)
    if context.get("activity"):
        # For demo, pretend activity could filter genres/artists in future
        pass
    if context.get("language"):
        query = query.filter(Track.language == context["language"])
    if context.get("country"):
        query = query.filter(Track.country == context["country"])
    # return top tracks (max 10)
    return query.order_by(Track.trending_score.desc()).limit(10).all()



# ------------------ ROUTES ------------------

# PUBLIC_INTERFACE
@app.get("/", tags=["Health"])
def health_check():
    """Simple health check endpoint."""
    return {"message": "MuseMap Backend is healthy."}

# PUBLIC_INTERFACE
@app.get("/db_health", tags=["Health"], summary="Database Connection Health", description="Check SQLite DB connectivity.")
def db_health():
    """
    Pings the SQLite database and returns status.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1")
        conn.close()
        return {"db_status": "healthy"}
    except Exception as ex:
        return {"db_status": "unhealthy", "error": str(ex)}


# ===== USER registration/profile =====
# PUBLIC_INTERFACE
@app.post("/register", tags=["User"], status_code=status.HTTP_201_CREATED, summary="Register User")
def register(user: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.
    """
    if get_user_by_username(db, user.username):
        raise HTTPException(status_code=400, detail="Username already exists.")
    if get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already exists.")
    hashed = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed,
        language_pref=user.language_pref,
        theme=user.theme or "light",
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"id": db_user.id, "username": db_user.username, "email": db_user.email}

# PUBLIC_INTERFACE
@app.post("/token", tags=["User"], summary="Login/User Token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login with username/password and get a fake token (for demo only, not JWT!).
    """
    user = get_user_by_username(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    # Demo only: in production use JWT
    return {"access_token": user.username + "token", "token_type": "bearer"}

# PUBLIC_INTERFACE
@app.get("/profile", response_model=UserProfileOut, tags=["User"], summary="Get User Profile")
def get_profile(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Get the currently logged-in user's profile info.
    (Simulated: extracts username from token for demo)
    """
    if not token or not token.endswith("token"):
        raise HTTPException(status_code=401, detail="Invalid token")
    username = token[:-5]
    user = get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# PUBLIC_INTERFACE
@app.put("/profile", tags=["User"], summary="Update Profile")
def update_profile(update: UserCreate, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Update user profile info: language/theme/email.
    """
    username = None
    if token and token.endswith("token"):
        username = token[:-5]
    user = get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.email = update.email
    user.language_pref = update.language_pref or user.language_pref
    user.theme = update.theme or user.theme
    db.commit()
    db.refresh(user)
    return {"message": "Profile updated."}


# ====== MUSIC DISCOVERY/Trending ======

# PUBLIC_INTERFACE
@app.get("/trending_tracks", response_model=List[TrendingTrackOut], tags=["Music"], summary="Get trending tracks on map")
def get_trending_tracks(db: Session = Depends(get_db)):
    """
    Retrieve trending tracks across different world locations for map view.
    """
    # In real app, group by country/city, now just demo a few
    trending_tracks = db.query(Track).order_by(Track.trending_score.desc()).limit(20).all()
    # For map: assume .country is location
    result = []
    for t in trending_tracks:
        result.append({
            "track": t,
            "location": t.country or "US"
        })
    return result

# ====== PLAYLIST GENERATION ======

# PUBLIC_INTERFACE
@app.post("/generate_playlist", response_model=PlaylistOut, tags=["Playlist"], summary="Generate Playlist Based on Context")
def generate_playlist(
    context: PlaylistCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Generate a playlist for the current user based on context selectors
    (activity, time, language, location).
    """
    # 1. Identify user
    if not token or not token.endswith("token"):
        raise HTTPException(status_code=401, detail="Invalid token")
    username = token[:-5]
    user = get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="Invalid user")
    # 2. Playlist generation (simulate; in real app, smarter algorithm)
    playlist_tracks = fake_generate_playlist({
        "activity": context.context_activity,
        "time": context.context_time,
        "language": context.context_language,
        "country": context.context_location
    }, db=db)
    # 3. Save playlist
    playlist_db = Playlist(
        name=context.name,
        context_activity=context.context_activity,
        context_time=context.context_time,
        context_language=context.context_language,
        context_location=context.context_location,
        owner_id=user.id
    )
    playlist_db.tracks = playlist_tracks
    db.add(playlist_db)
    db.commit()
    db.refresh(playlist_db)
    return playlist_db

# PUBLIC_INTERFACE
@app.get("/my_playlists", response_model=List[PlaylistOut], tags=["Playlist"], summary="User's Saved Playlists")
def get_my_playlists(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Returns all playlists for the logged-in user.
    """
    if not token or not token.endswith("token"):
        raise HTTPException(status_code=401, detail="Invalid token")
    username = token[:-5]
    user = get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.playlists

# PUBLIC_INTERFACE
@app.get("/playlists/{playlist_id}", response_model=PlaylistOut, tags=["Playlist"], summary="Get One Playlist")
def get_playlist(playlist_id: int, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Retrieve a specific playlist by ID (user-owned).
    """
    if not token or not token.endswith("token"):
        raise HTTPException(status_code=401, detail="Invalid token")
    username = token[:-5]
    user = get_user_by_username(db, username)
    p = db.query(Playlist).filter(Playlist.id == playlist_id, Playlist.owner_id == user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return p

# PUBLIC_INTERFACE
@app.delete("/playlists/{playlist_id}", tags=["Playlist"], summary="Delete Playlist")
def delete_playlist(playlist_id: int, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Delete a playlist by ID for the logged-in user.
    """
    if not token or not token.endswith("token"):
        raise HTTPException(status_code=401, detail="Invalid token")
    username = token[:-5]
    user = get_user_by_username(db, username)
    p = db.query(Playlist).filter(Playlist.id == playlist_id, Playlist.owner_id == user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Playlist not found")
    db.delete(p)
    db.commit()
    return {"message": "Playlist deleted"}


# ========== DB INITIALIZATION ==========
def seed_initial_data():
    """
    Seed the database with some demo tracks on first run for music discovery.
    """
    db = SessionLocal()
    tracks_exist = db.query(Track).count() > 0
    if not tracks_exist:
        demo_tracks = [
            Track(
                title="Sunrise Groove", artist="DJ Solar", album="Morning Vibes",
                duration=180, language="en", country="US", trending_score=87,
                external_url="https://example.com/tracks/1"
            ),
            Track(
                title="Noches Latinas", artist="La Fiesta", album="Latin Nights",
                duration=200, language="es", country="ES", trending_score=84,
                external_url="https://example.com/tracks/2"
            ),
            Track(
                title="Tokyo Beat", artist="Synthwave", album="City Pulse",
                duration=210, language="ja", country="JP", trending_score=80,
                external_url="https://example.com/tracks/3"
            ),
            Track(
                title="Afro Pop", artist="Djembe Crew", album="Across Africa",
                duration=215, language="en", country="NG", trending_score=78,
                external_url="https://example.com/tracks/4"
            ),
            Track(
                title="Paris Café", artist="Chanson Belle", album="Jour de Fête",
                duration=175, language="fr", country="FR", trending_score=74,
                external_url="https://example.com/tracks/5"
            ),
        ]
        db.bulk_save_objects(demo_tracks)
        db.commit()
    db.close()


# ---- DB Setup ----
def init_db():
    Base.metadata.create_all(bind=engine)
    seed_initial_data()


@app.on_event("startup")
def on_startup():
    init_db()

# ------------- EXPLICIT OPENAPI ROUTE for WebSocket/Realtime (for completeness) -------------
@app.get("/ws_usage", tags=["Health"], summary="WebSocket Realtime Info", description="Note: All real-time features are to be implemented client-side via polling; there are NO websocket endpoints in v1. Use REST endpoints only for all features.")
def ws_usage():
    return {"message": "Realtime APIs are not implemented as WS for this release."}
