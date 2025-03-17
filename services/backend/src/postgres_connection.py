import psycopg, psycopg_binary, uuid
from psycopg_pool import AsyncConnectionPool
import asyncio
from schemas import *


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        if not self.pool:
            max_retries = 10
            retry_delay = 2  # seconds
            for attempt in range(max_retries):
                try:
                    print(f"Attempting Postgres connection, try {attempt + 1}/{max_retries}")
                    self.pool = AsyncConnectionPool(
                        "dbname=postgres2 user=postgres password=*host_pwd* host=*host_ip* port=5432",
                        min_size=1,
                        max_size=20,
                        open=False  # We'll open it explicitly
                    )
                    await self.pool.open()
                    print("Postgres pool connected successfully")
                    break
                except Exception as err:
                    print(f"Postgres pool connection failed: \n{err}")
                    await asyncio.sleep(retry_delay)
            if not self.pool:
                raise Exception("Failed to establish connection pool after retries")
            # No autocommit on pool level; handle in transactions

    async def init_learning_path(self) -> str:
        lp_id = str(uuid.uuid4())
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                sql = "INSERT INTO learning_paths (id) VALUES (%s)"
                await cur.execute(sql, (lp_id,))
                await conn.commit()
        return lp_id

    async def init_user(self, user: InitiationUserData, lp_id: str) -> User:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                sql = """
                    INSERT INTO users (username, email, birth_date, hashed_password, learning_path_id)
                    VALUES (%s, %s, %s, %s, %s)
                """
                await cur.execute(sql, (user.username, user.email, user.birth_date, user.hashed_password, lp_id))
                await conn.commit()

    async def fetch_user_info(self, username: str) -> User | None:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                sql = "SELECT * FROM users WHERE username = %s"
                await cur.execute(sql, (username,))
                row = await cur.fetchone()
                return User(**dict(row)) if row else None

    async def delete_user(self, user_id: str):
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                sql = "DELETE FROM users WHERE id = %s"
                await cur.execute(sql, (user_id,))
                await conn.commit()

    async def get_learning_path_id(self, user_id: str) -> str | None:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                sql = "SELECT learning_path_id FROM users WHERE id = %s"
                await cur.execute(sql, (user_id,))
                row = await cur.fetchone()
                return row[0] if row else None

    async def fetch_learning_path_position(self, lp_id: str) -> LearningPath | None:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                sql = "SELECT current_level, current_lesson_part WHERE id = %s"
                await cur.execute(sql, (lp_id,))
                row = await cur.fetchone()
                return LearningPath(lp_id, **dict(row)) if row else None

    async def update_learning_path_position(self, learning_path_id: str, current_level: int, current_lesson_part: int):
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                sql = """
                    UPDATE learning_paths
                    SET current_level = %s,
                        current_lesson_part = %s
                    WHERE id = %s
                """
                await cur.execute(sql, (current_level, current_lesson_part, learning_path_id))
                await conn.commit()

    async def append_lesson_verdict(self, learning_path_id: str, verdict: LessonVerdict):
        partial_verdicts_json = [pv.dict() for pv in verdict.partial_verdicts]
        verdict_tuple = (
            verdict.total_score,
            verdict.vehicles,
            verdict.current_part_id,
            partial_verdicts_json,
            verdict.comment
        )
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                sql = """
                    UPDATE learning_paths
                    SET lessons_verdicts = array_append(lessons_verdicts, %s::lesson_verdict)
                    WHERE id = %s
                """
                await cur.execute(sql, (verdict_tuple, learning_path_id))
                await conn.commit()

    async def update_last_lesson_verdict(self, learning_path_id: str, verdict: LessonVerdict):
        vehicles_json = [v.dict() for v in verdict.vehicles] if verdict.vehicles else []
        partial_verdicts_json = [pv.dict() for pv in verdict.partial_verdicts]
        verdict_tuple = (
            verdict.total_score,
            vehicles_json,
            verdict.current_part_id,
            partial_verdicts_json,
            verdict.comment
        )
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                sql = """
                    UPDATE learning_paths
                    SET lessons_verdicts = array_remove(lessons_verdicts, lessons_verdicts[array_length(lessons_verdicts, 1) - 1]) || ARRAY[%s::lesson_verdict]
                    WHERE id = %s
                """
                await cur.execute(sql, (verdict_tuple, learning_path_id))
                await conn.commit()

    async def save_vehicle(self, user_id: str, lesson_id: int, lesson_part: int, vehicle_description: VehicleSchema):
        pass

    async def fetch_learning_material(self, lesson_id: int, lesson_part: int):
        # Under construction
        return None

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None
            print("Connection pool closed")

postgres = Database()
postgres.connect()
    
