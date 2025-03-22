from pydantic import BaseModel
from datetime import date
from enum import Enum
from uuid import UUID

class SubscriptionType(Enum):
    FREE = 0
    PAID = 1

class User(BaseModel):
    id: UUID
    username: str
    email: str
    birth_date: date | None
    learning_path_id: UUID
    total_score: int
    subscription_id: SubscriptionType # say, defaults to 0
    hashed_password: str

class CommandData(BaseModel):
    float_params: dict[str, float]
    vector3_params: dict[str, tuple] # for now we'll not use the {x: _, y: _, z: _} format
    string_params: dict[str, str]
    bool_params: dict[str, bool]

class VehicleSchema(BaseModel):
    movement_coding: list[CommandData]
    blocks_coordinates: list[dict]

class LessonPartVerdict(BaseModel):
    lesson_part_id: int
    lesson_part_name: str
    score: int
    comment: str
    finished: bool

class LessonVerdict(BaseModel):
    total_score: int
    vehicles: list[VehicleSchema | None]
    current_part_id: int # -1 means finished
    partial_verdicts: list[LessonPartVerdict]
    comment: str

class LearningPath(BaseModel):
    id: UUID
    current_level: int
    current_lesson_part: int

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class InitiationUserData(BaseModel):
    username: str
    email: str
    birth_date: date
    hashed_password: str

class UpdateUserInfoRequest(BaseModel):
    username: str
    email: str
    birth_date: date

class UpdatePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class UpdateSubscriptionRequest(BaseModel):
    password: str
    new_subscription_status: SubscriptionType

class SignUpRequest(BaseModel):
    username: str
    email: str
    birth_date: date
    password: str
