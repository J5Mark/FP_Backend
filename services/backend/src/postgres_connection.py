import psycopg, psycopg_binary, uuid
from psycopg_pool import AsyncConnectionPool
import asyncio
from schemas import *
import logging
from psycopg.rows import dict_row

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool = AsyncConnectionPool(
            conninfo="host=localhost port=5432 dbname=postgres user=postgres password=fuckfuckfuck",
            min_size=1,      
            max_size=10,      
            timeout=30,       
            max_lifetime=1800, # Refresh connections after 30 minutes
            kwargs={
                "autocommit": True, 
                "options": "-c tcp_keepalives_idle=30 -c tcp_keepalives_interval=10 -c tcp_keepalives_count=5"  # TCP keepalives
            }
        )
        asyncio.create_task(self._open_pool())

    async def _open_pool(self):
        max_retries = 4
        retry_delay = 2  # seconds
        for attempt in range(max_retries):
            try:
                logger.info(f"Opening connection pool, attempt {attempt + 1}/{max_retries}")
                await self.pool.wait()
                logger.info("Postgres connection pool initialized successfully")
                return
            except Exception as err:
                logger.error(f"Pool initialization failed: {err}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
        raise Exception("Failed to initialize connection pool after all retries")

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
                    INSERT INTO users (username, email, birth_date, hashed_pwd, learning_path_id)
                    VALUES (%s, %s, %s, %s, %s)
                """
                await cur.execute(sql, (user.username, user.email, user.birth_date, user.hashed_password, lp_id))
                await conn.commit()

    async def fetch_user_info(self, username: str) -> User | None:
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                sql = "SELECT * FROM users WHERE username = %s"
                await cur.execute(sql, (username,))
                row = await cur.fetchone()
                if not row: return None
                row["hashed_password"] = row.pop("hashed_pwd") # test if works
                logger.debug(f"row retrieved: {row}")
                return User(**row) if row else None

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

    async def fetch_user_info_by_id(self, user_id: str) -> User:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                sql = "SELECT * FROM users WHERE id = %s"
                await cur.execute(sql, (user_id,))
                row = await cur.fetchone()
                return User(**dict(row)) if row else None

    async def update_user_info(self, user_id: str, username: str | None=None, email: str | None=None, birth_date: date | None=None) -> User | None:
        updates = {"username": username, "email": email, "birth_date": birth_date}
        if not any(list(updates.values())):
            return await self.fetch_user_info_by_id(username)
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                set_clause = ", ".join(f"{key} = %s" for key in updates)
                sql = f"UPDATE users SET {set_clause} WHERE id = %s RETURNING *"
                await cur.execute(sql, list(updates.values())+[user_id])
                row = await cur.fetchone()
                await conn.commit()
                return User(**dict(row)) if row else None

    async def update_user_password(user_id: str, hashed_password: str) -> bool:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                sql = "UPDATE users SET hashed_pwd = %s WHERE id = %s RETURNING id"
                await cur.execute(sql, (hashed_password, user_id))
                row = await cur.fetchone()
                await conn.commit()
                return bool(row)

    async def update_user_subscription_plan(user_id: str, subscription_plan: SubscriptionType) -> User:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                sql = "UPDATE users SET subscription_id = %s WHERE id = %s, RETURNING *"
                await cur.execute(sql, (subscription_plan, user_id))
                row = await cur.fetchone()
                await conn.commit()
                return User(**dict(row)) if row else None

    async def save_vehicle(self, user_id: str, lesson_id: int, lesson_part: int, vehicle_description: VehicleSchema):
        pass

    async def fetch_learning_material(self, lesson_id: int, lesson_part: int):
        # Under construction
        return None

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None
            

postgres = Database()
