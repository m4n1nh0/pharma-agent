"""Endpoints HTTP de autenticação — delega a lógica ao AuthService."""

from fastapi import APIRouter, Depends
from src.application.services.auth_service import auth_service
from src.application.use_cases.dtos import UserCreateDTO, UserLoginDTO, TokenResponseDTO, RefreshRequestDTO, UserResponseDTO
from src.presentation.api.middleware.auth_dependency import get_current_user

router = APIRouter(prefix="/auth", tags=["Autenticação"])


def _token_response(user: dict) -> TokenResponseDTO:
    return TokenResponseDTO(
        access_token=auth_service.create_access_token(user),
        refresh_token=auth_service.create_refresh_token(user),
        user=UserResponseDTO(
            id=user["id"], name=user["name"], email=user["email"],
            role=user["role"], crm_crf=user.get("crm_crf"), created_at=user["created_at"],
        ),
    )


@router.post("/register", response_model=TokenResponseDTO, status_code=201)
async def register(data: UserCreateDTO):
    user = auth_service.register(data.name, data.email, data.password, data.role, data.crm_crf)
    return _token_response(user)


@router.post("/login", response_model=TokenResponseDTO)
async def login(data: UserLoginDTO):
    user = auth_service.authenticate(data.email, data.password)
    return _token_response(user)


@router.post("/refresh", response_model=TokenResponseDTO)
async def refresh(data: RefreshRequestDTO):
    payload = auth_service.decode_token(data.refresh_token)
    user = auth_service.get_by_id(payload["sub"])
    return _token_response(user)


@router.get("/me", response_model=UserResponseDTO)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponseDTO(
        id=current_user["id"], name=current_user["name"], email=current_user["email"],
        role=current_user["role"], crm_crf=current_user.get("crm_crf"), created_at=current_user["created_at"],
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    return {"message": f"Até logo, {current_user['name'].split()[0]}!", "status": "logged_out"}
