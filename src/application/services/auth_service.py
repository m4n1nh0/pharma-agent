"""Regras de negócio de autenticação: criação de tokens, validação, hashing."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status

from src.config.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Banco em memória — substitua por PostgreSQL/SQLAlchemy em produção
USERS_DB: dict[str, dict] = {
    "demo@pharma.com": {
        "id": "usr_001",
        "name": "Dr. Demo Farmacêutico",
        "email": "demo@pharma.com",
        "hashed_password": pwd_context.hash("demo123"),
        "role": "farmaceutico",
        "crm_crf": "CRF-SE 12345",
        "created_at": "2024-01-15T10:00:00Z",
    },
    "medico@pharma.com": {
        "id": "usr_002",
        "name": "Dr. Carlos Médico",
        "email": "medico@pharma.com",
        "hashed_password": pwd_context.hash("medico123"),
        "role": "medico",
        "crm_crf": "CRM-SE 54321",
        "created_at": "2024-01-20T08:30:00Z",
    },
}


class AuthService:
    """Operações de autenticação e gestão de usuários."""

    # ── Password ──────────────────────────────────────────────────────────────
    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    # ── Tokens ────────────────────────────────────────────────────────────────
    @staticmethod
    def _create_token(data: dict, expires_delta: timedelta) -> str:
        payload = {
            **data,
            "exp": datetime.now(timezone.utc) + expires_delta,
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    @classmethod
    def create_access_token(cls, user: dict) -> str:
        return cls._create_token(
            {"sub": user["id"], "email": user["email"], "role": user["role"], "type": "access"},
            timedelta(minutes=settings.access_token_expire_minutes),
        )

    @classmethod
    def create_refresh_token(cls, user: dict) -> str:
        return cls._create_token(
            {"sub": user["id"], "email": user["email"], "type": "refresh"},
            timedelta(days=settings.refresh_token_expire_days),
        )

    @staticmethod
    def decode_token(token: str) -> dict:
        try:
            return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token inválido ou expirado: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # ── Usuários ──────────────────────────────────────────────────────────────
    @staticmethod
    def get_by_email(email: str) -> Optional[dict]:
        return USERS_DB.get(email)

    @staticmethod
    def get_by_id(user_id: str) -> Optional[dict]:
        return next((u for u in USERS_DB.values() if u["id"] == user_id), None)

    @classmethod
    def authenticate(cls, email: str, password: str) -> dict:
        user = cls.get_by_email(email)
        if not user or not cls.verify_password(password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais inválidas",
            )
        return user

    @classmethod
    def register(cls, name: str, email: str, password: str, role: str, crm_crf: Optional[str]) -> dict:
        if cls.get_by_email(email):
            raise HTTPException(status_code=400, detail="E-mail já cadastrado")
        import uuid
        user = {
            "id": f"usr_{uuid.uuid4().hex[:8]}",
            "name": name,
            "email": email,
            "hashed_password": cls.hash_password(password),
            "role": role,
            "crm_crf": crm_crf,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        USERS_DB[email] = user
        return user


auth_service = AuthService()
