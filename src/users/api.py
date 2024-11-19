from typing import Optional
from ninja import Router, Schema
from ninja_jwt.controller import NinjaJWTDefaultController
from django.contrib.auth import get_user_model, authenticate
from ninja.security import HttpBearer
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.tokens import RefreshToken
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from django.core.signing import TimestampSigner
from django.core import exceptions

from users.models import Role

User = get_user_model()
router = Router()
jwt_controller = NinjaJWTDefaultController()

class TokenSchema(Schema):
    access: str
    refresh: str

class AuthSchema(Schema):
    email: str
    password: str

class UserSchema(Schema):
    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    phone_number: Optional[str] = None
    climbing_level: Optional[str] = None

class UserResponseSchema(Schema):
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    date_of_birth: Optional[str]
    phone_number: Optional[str]
    climbing_level: Optional[str]

class PasswordResetRequestSchema(Schema):
    email: str

class PasswordResetConfirmSchema(Schema):
    token: str
    email: str
    new_password: str

class EmailVerificationSchema(Schema):
    token: str

class ProfileUpdateSchema(Schema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    phone_number: Optional[str] = None
    climbing_level: Optional[str] = None
    avatar: Optional[str] = None

class RoleAssignmentSchema(Schema):
    role_name: str

class RegistrationStatusSchema(Schema):
    enabled: bool
    message: Optional[str] = None

@router.get("/registration-status", response=RegistrationStatusSchema)
def get_registration_status(request):
    return {
        "enabled": getattr(settings, "ALLOW_REGISTRATION", True),
        "message": "Registration is currently disabled" if not getattr(settings, "ALLOW_REGISTRATION", True) else None
    }

@router.post("/register", response=UserResponseSchema)
def register_user(request, data: UserSchema):
    """Register new user with email/password"""
    if not getattr(settings, "ALLOW_REGISTRATION", True):
        raise exceptions.ValidationError(
            {"detail": "Registration is currently disabled"}
        )
        
    user = User.objects.create_user(
        username=data.email,
        email=data.email,
        password=data.password,
        first_name=data.first_name or '',
        last_name=data.last_name or ''
    )
    return user

@router.post("/login", response=TokenSchema)
def login(request, data: AuthSchema):
    user = authenticate(username=data.email, password=data.password)
    if user is None:
        return {"detail": "Invalid credentials"}, 401
    
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh)
    }

@router.post("/token/refresh", response=TokenSchema)
def refresh_token(request, refresh_token: str):
    refresh = RefreshToken(refresh_token)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh)
    }

@router.get("/me", response=UserResponseSchema, auth=JWTAuth())
def get_current_user(request):
    return request.auth

@router.post("/password/reset")
def request_password_reset(request, data: PasswordResetRequestSchema):
    """Send password reset email"""
    # Add password reset logic
    pass

@router.post("/password/reset/confirm")
def confirm_password_reset(request, token: str, new_password: str):
    # Reset password logic
    pass

@router.post("/verify-email")
def verify_email(request, data: EmailVerificationSchema):
    """Verify user's email address"""
    # Add email verification logic
    pass

@router.put("/profile", response=UserResponseSchema, auth=JWTAuth())
def update_profile(request, data: ProfileUpdateSchema):
    user = request.auth
    for field, value in data.dict(exclude_unset=True).items():
        setattr(user, field, value)
    user.save()
    return user

@router.get("/profile/{user_id}", response=UserResponseSchema, auth=JWTAuth())
def get_user_profile(request, user_id: int):
    try:
        user = User.objects.get(id=user_id)
        return user
    except User.DoesNotExist:
        return {"error": "User not found"}, 404

@router.post("/role/{user_id}", auth=JWTAuth())
def assign_role(request, user_id: int, data: RoleAssignmentSchema):
    if not request.auth.is_superuser:
        return {"error": "Unauthorized"}, 403
        
    try:
        user = User.objects.get(id=user_id)
        role = Role.objects.get(name=data.role_name)
        user.role = role
        user.save()
        return {"message": f"Role {role.name} assigned to user successfully"}
    except (User.DoesNotExist, Role.DoesNotExist):
        return {"error": "User or Role not found"}, 404

@router.get("/sessions")
def list_active_sessions(request):
    # Return user's active sessions
    pass

@router.post("/sessions/revoke")
def revoke_session(request, session_id: str):
    # Revoke specific session
    pass

# JWT endpoints are automatically added by ninja_jwt 