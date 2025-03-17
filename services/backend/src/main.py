from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import os
from datetime import datetime, timedelta
from schemas import *
from jose import JWTError, jwt
from passlib.context import CryptContext
from postgres_connection import postgres

SECRET_KEY = "2d73d6bc2ad2aa817f237aae3ae99ffa6342b945b633e1e06ba3847e9bebf7ff" # left it here for now, later will move to a safe place
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


pwd_context = CryptContext(schemes=["bcrypt"], deprecated = "auto")
oauth_2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(pwd):
    return pwd_context.hash(pwd)

async def authenticate_user(username: str, password: str) -> User:
    user = await postgres.fetch_user_info(username=username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False

    return user

def create_access_token(data: dict, expires_delta: timedelta | None=None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth_2_scheme)) -> User:
    credential_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                                         detail="Could not validate credentials", 
                                         headers={"WWW-Authenticate": "Bearer"})
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credential_exception

        token_data = TokenData(username=username)
    except JWTError:
        raise credential_exception

    user = await postgres.fetch_user_info(token_data.username)
    if user is None:
        raise credential_exception
    
    return user


app = FastAPI()


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires)
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/signup")
async def signup_user(username: str, email: str, birth_date: datetime, password: str) -> dict:
    existing_user = await postgres.fetch_user_info(username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")

    hashed_password = get_password_hash(password)
    lp_id = await postgres.init_learning_path()

    await postgres.init_user(InitiationUserData(username, email, birth_date, hashed_password),
                             lp_id)

    return {"status": f"User {username} registered!"}


@app.post("/save_progress")
async def save_progress(
    verdict: LessonVerdict,
    vehicle_used: VehicleSchema | None = None,
    current_user: User = Depends(get_current_user)
):
    # Ensure vehicles is a list
    if verdict.vehicles is None:
        verdict.vehicles = []
    if vehicle_used:
        verdict.vehicles.append(vehicle_used)

    lp_id = await postgres.get_learning_path_id(current_user.id)
    if not lp_id:
        raise HTTPException(status_code=404, detail="Learning path not found")

    # Fetch current position
    current_position = await postgres.fetch_learning_path_position(lp_id)
    if not current_position: raise HTTPException(status_code=404, detail="Position on learning path not found")

    if verdict.current_part_id == -1:  # Lesson finished
        await postgres.update_learning_path_position(
            lp_id, current_position.current_level + 1, 0
        )
        await postgres.append_lesson_verdict(lp_id, verdict)
    else:
        await postgres.update_learning_path_position(
            lp_id, current_position.current_level, verdict.current_part_id
        )
        await postgres.update_last_lesson_verdict(lp_id, verdict)

    return {"status": f"User {current_user.id} progress saved"}