from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import os
import bcrypt
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = "2d73d6bc2ad2aa817f237aae3ae99ffa6342b945b633e1e06ba3847e9bebf7ff"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

load_dotenv()

class User(BaseModel):
    username: str
    email: str
    password: str
    disabled: bool

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class UserInDB(User):
    hashed_password: str

db = {
    "tits": {
        "username": "tits",
        "email": "boobs@tits.cum",
        "password": "8008558008",
        "hashed_password": "$2b$12$gcEC8z9nLEkzYC2VeMuZw.qtxuuGMcgAjDz/.N6Kkt4o5LWeRsWnW",
        "disabled": False
    }
}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated = "auto")
oauth_2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(pwd):
    return pwd_context.hash(pwd)

def get_user(db, username: str):
    if username in db:
        user_data = db[username]
        return UserInDB(**user_data)  # ?? Is this syntax legit ??

def authenticate_user(db, username: str, password: str):
    user = get_user(db, username)
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
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM) # will have to figure out what data jwt wants/needs to encode here

    return encoded_jwt


async def get_current_user(token: str = Depends(oauth_2_scheme)):
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

    user = get_user(db, username=token_data.username)
    if user is None:
        raise credential_exception
    
    return user

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")

    return current_user

app = FastAPI()


@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, 
                            detail="incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires)
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

