from typing import Optional, List
from datetime import date
from ninja import Router, Schema
from ninja_jwt.controller import NinjaJWTDefaultController
from django.contrib.auth import get_user_model, authenticate
from ninja.security import HttpBearer
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.tokens import RefreshToken
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from django.core import exceptions
from django.shortcuts import get_object_or_404
from django.db import models
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from ninja.errors import HttpError

from competitions.api import CompetitionOut
from leagues.schemas import LeagueOut
from users.models import Role
from competitions.models import Competition
from users.models import UserAuditLog

User = get_user_model()
router = Router(auth=JWTAuth())

class TokenSchema(Schema):
    access: str
    refresh: str

class AuthSchema(Schema):
    email: str
    password: str

class UserSchema(Schema):
    email: str
    password: str
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    phone: Optional[str] = None
    climbing_level: Optional[str] = None

    class Config:
        json_encoders = {
            date: lambda v: v.strftime('%Y-%m-%d')
        }

class UserResponseSchema(Schema):
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    phone: Optional[str] = None
    climbing_level: Optional[str] = None

    class Config:
        json_encoders = {
            date: lambda v: v.strftime('%Y-%m-%d')
        }

class PasswordResetRequestSchema(Schema):
    email: str

class PasswordResetConfirmSchema(Schema):
    email: str
    token: str
    new_password: str

    def validate_new_password(self, value):
        try:
            # Use Django's password validation
            validate_password(value)
            return value
        except ValidationError as e:
            raise ValueError(str(e.messages[0]))

class EmailVerificationSchema(Schema):
    token: str

class ValidationErrorSchema(Schema):
    field_errors: dict[str, List[str]]
    message: str

class ProfileUpdateSchema(Schema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    phone_number: Optional[str] = None
    climbing_level: Optional[str] = None
    avatar: Optional[str] = None

    @staticmethod
    def validate_phone_number(value: str) -> str:
        if value and not value.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            raise ValueError("Phone number must contain only digits, spaces, hyphens, and '+' symbol")
        return value

    @staticmethod
    def validate_date_of_birth(value: date) -> date:
        if value and value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value

class RoleAssignmentSchema(Schema):
    role_name: str

class RegistrationStatusSchema(Schema):
    enabled: bool
    message: Optional[str] = None

class UserLeagueSchema(Schema):
    league_id: int
    role: str  # 'athlete' or 'official'
    categories: List[str]

class UserLeagueResponseSchema(Schema):
    leagues_as_athlete: List[LeagueOut]
    leagues_as_official: List[LeagueOut]
    total_competitions: int
    current_rankings: dict

class AuditLogSchema(Schema):
    id: int
    user_id: Optional[int]
    action: str
    details: dict
    ip_address: str
    timestamp: str

class AuditLogFilterSchema(Schema):
    user_id: Optional[int] = None
    action: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    ip_address: Optional[str] = None

class RefreshTokenSchema(Schema):
    refresh: str

@router.get("/registration-status", response=RegistrationStatusSchema, auth=None)
def get_registration_status(request):
    return {
        "enabled": getattr(settings, "ALLOW_REGISTRATION", True),
        "message": "Registration is currently disabled" if not getattr(settings, "ALLOW_REGISTRATION", True) else None
    }

@router.post("/register", response=UserResponseSchema, auth=None)
def register_user(request, data: UserSchema):
    """Register new user with email/password"""
    if not getattr(settings, "ALLOW_REGISTRATION", True):
        raise exceptions.ValidationError(
            {"detail": "Registration is currently disabled"}
        )
    
    # Handle name field if provided
    if data.name and not (data.first_name or data.last_name):
        # Split full name into first and last name
        name_parts = data.name.split(maxsplit=1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''
    else:
        first_name = data.first_name or ''
        last_name = data.last_name or ''
        
    user = User.objects.create_user(
        username=data.email,
        email=data.email,
        password=data.password,
        first_name=first_name,
        last_name=last_name,
        phone=data.phone or '',
        date_of_birth=data.date_of_birth,
        climbing_level=data.climbing_level or ''
    )
    
    # Explicitly create response dict to match schema
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "date_of_birth": user.date_of_birth,
        "phone": user.phone,
        "climbing_level": user.climbing_level
    }

@router.post("/login", response=TokenSchema, auth=None)
def login(request, data: AuthSchema):
    user = authenticate(username=data.email, password=data.password)
    if user is None:
        raise HttpError(401, "Invalid credentials")
    
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh)
    }

@router.post("/token/refresh", response=TokenSchema, auth=None)
def refresh_token(request, data: RefreshTokenSchema):
    try:
        refresh = RefreshToken(data.refresh)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        }
    except Exception as e:
        raise HttpError(401, "Invalid refresh token")

@router.get("/me", response=UserResponseSchema, auth=JWTAuth())
def get_current_user(request):
    return request.auth

@router.post("/password/reset", response=dict, auth=None)
def request_password_reset(request, data: PasswordResetRequestSchema):
    """Send password reset email"""
    # TODO: Implement proper password reset functionality
    return {"message": "Password reset request received"}

@router.post("/password/reset/confirm", response=dict)
def confirm_password_reset(request, data: PasswordResetConfirmSchema):
    """Confirm password reset with token"""
    try:
        user = User.objects.get(email=data.email)
        
        # Verify the token
        if not default_token_generator.check_token(user, data.token):
            # Log failed attempt
            UserAuditLog.objects.create(
                user=user,
                action='password_reset_failed',
                details={
                    'reason': 'invalid_token',
                    'ip_address': request.META.get('REMOTE_ADDR'),
                    'user_agent': request.META.get('HTTP_USER_AGENT')
                },
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return {"error": "Invalid or expired token"}, 400
        
        try:
            # Validate password strength
            validate_password(data.new_password, user=user)
        except ValidationError as e:
            # Log failed attempt due to password validation
            UserAuditLog.objects.create(
                user=user,
                action='password_reset_failed',
                details={
                    'reason': 'password_validation',
                    'validation_error': str(e.messages[0]),
                    'ip_address': request.META.get('REMOTE_ADDR'),
                    'user_agent': request.META.get('HTTP_USER_AGENT')
                },
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return {"error": str(e.messages[0])}, 400
            
        # Set new password
        user.set_password(data.new_password)
        user.save()
        
        # Invalidate all existing sessions
        user.session_set.all().delete()
        
        # Log the successful password reset
        UserAuditLog.objects.create(
            user=user,
            action='password_reset_success',
            details={
                'method': 'email_token',
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT')
            },
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return {"message": "Password successfully reset"}
    except User.DoesNotExist:
        # Log attempt with non-existent email
        UserAuditLog.objects.create(
            user=None,
            action='password_reset_failed',
            details={
                'reason': 'invalid_email',
                'attempted_email': data.email,
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT')
            },
            ip_address=request.META.get('REMOTE_ADDR')
        )
        return {"error": "Invalid email"}, 400

@router.post("/verify-email", response=dict)
def verify_email(request, data: EmailVerificationSchema):
    """Verify user's email address"""
    signer = TimestampSigner()
    try:
        email = signer.unsign(data.token, max_age=86400)  # 24 hour expiry
        user = User.objects.get(email=email)
        
        if not user.email_verified:
            user.email_verified = True
            user.save()
            
            # Log the email verification
            UserAuditLog.objects.create(
                user=user,
                action='email_verified',
                details={
                    'method': 'email_token',
                    'ip_address': request.META.get('REMOTE_ADDR'),
                    'user_agent': request.META.get('HTTP_USER_AGENT')
                },
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
        return {"message": "Email successfully verified"}
    except (SignatureExpired, BadSignature, User.DoesNotExist):
        return {"error": "Invalid or expired verification token"}, 400

@router.post("/resend-verification", response=dict, auth=None)
def resend_verification_email(request, data: PasswordResetRequestSchema):
    """Resend verification email"""
    try:
        user = User.objects.get(email=data.email)
        if user.email_verified:
            return {"message": "Email is already verified"}
            
        # Generate verification token
        signer = TimestampSigner()
        token = signer.sign(user.email)
        
        # Create verification URL
        verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        
        # Prepare email content
        context = {
            'user': user,
            'verify_url': verify_url,
            'valid_hours': 24
        }
        html_message = render_to_string('email_verification.html', context)
        plain_message = strip_tags(html_message)
        
        # Send verification email
        send_mail(
            subject='Verify Your Email',
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        # Log the verification email resend
        UserAuditLog.objects.create(
            user=user,
            action='verification_email_resent',
            details={
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT')
            },
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return {"message": "Verification email sent"}
    except User.DoesNotExist:
        # Return success for security reasons
        return {"message": "If an account exists with this email, verification instructions have been sent"}

@router.put("/profile", response={200: UserResponseSchema, 422: ValidationErrorSchema}, auth=JWTAuth())
def update_profile(request, data: ProfileUpdateSchema):
    user = request.auth
    try:
        # Create a dictionary of updates, excluding None values
        updates = {k: v for k, v in data.dict(exclude_unset=True).items() if v is not None}
        
        # Handle phone_number field name difference
        if 'phone_number' in updates:
            updates['phone'] = updates.pop('phone_number')
            
        for field, value in updates.items():
            setattr(user, field, value)
            
        user.full_clean()  # Validate the model
        user.save()
        
        return 200, user
        
    except ValidationError as e:
        # Convert Django's ValidationError to our format
        field_errors = {}
        for field, errors in e.error_dict.items():
            field_errors[field] = [err.message for err in errors]
        
        return 422, {
            "field_errors": field_errors,
            "message": "Validation error occurred"
        }
    except Exception as e:
        # Handle any other unexpected errors
        return 422, {
            "field_errors": {"non_field_errors": [str(e)]},
            "message": "An error occurred while updating the profile"
        }

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

@router.get("/me/leagues", response=UserLeagueResponseSchema, auth=JWTAuth())
def get_user_leagues(request):
    """Get all leagues associated with the current user"""
    user = request.auth
    return {
        "leagues_as_athlete": user.participating_leagues.all(),
        "leagues_as_official": user.officiating_leagues.all(),
        "total_competitions": user.competition_history.count() if hasattr(user, 'competition_history') else 0,
        "current_rankings": {}  # Implement ranking aggregation logic
    }

@router.post("/me/leagues/{league_id}/join", auth=JWTAuth())
def join_league(request, league_id: int, data: UserLeagueSchema):
    """Join a league as either athlete or official"""
    user = request.auth
    league = get_object_or_404(League, id=league_id)
    
    if data.role == 'athlete':
        league.athletes.add(user)
        if hasattr(user, 'profile'):
            user.profile.athlete_categories.extend(data.categories)
            user.profile.save()
    elif data.role == 'official' and user.has_role('official'):
        league.officials.add(user)
    else:
        return {"error": "Invalid role or insufficient permissions"}, 400
    
    return {"success": True}

@router.get("/me/competitions", response=List[CompetitionOut], auth=JWTAuth())
def get_user_competitions(request):
    """Get all competitions associated with the current user"""
    user = request.auth
    return Competition.objects.filter(
        models.Q(league__athletes=user) | 
        models.Q(league__officials=user)
    ).distinct()

@router.get("/audit-logs", response=List[AuditLogSchema], auth=JWTAuth())
def get_audit_logs(request, filters: AuditLogFilterSchema = None):
    """
    Get audit logs with optional filtering.
    Only accessible by superusers and users viewing their own logs.
    """
    if not request.auth.is_superuser:
        # Regular users can only view their own logs
        if filters and filters.user_id and filters.user_id != request.auth.id:
            return {"error": "Unauthorized to view other users' logs"}, 403
        filters.user_id = request.auth.id

    # Start with all logs
    logs = UserAuditLog.objects.all()

    # Apply filters
    if filters:
        if filters.user_id:
            logs = logs.filter(user_id=filters.user_id)
        if filters.action:
            logs = logs.filter(action=filters.action)
        if filters.start_date:
            logs = logs.filter(timestamp__gte=filters.start_date)
        if filters.end_date:
            logs = logs.filter(timestamp__lte=filters.end_date)
        if filters.ip_address:
            logs = logs.filter(ip_address=filters.ip_address)

    # Order by most recent first
    logs = logs.order_by('-timestamp')

    return logs

@router.get("/audit-logs/actions", response=List[str], auth=JWTAuth())
def get_audit_log_actions(request):
    """Get list of all possible audit log actions"""
    return UserAuditLog.objects.values_list('action', flat=True).distinct()

@router.get("/audit-logs/summary", response=dict, auth=JWTAuth())
def get_audit_logs_summary(request):
    """Get summary statistics of audit logs"""
    if not request.auth.is_superuser:
        return {"error": "Unauthorized"}, 403

    # Get total counts for different actions
    action_counts = (
        UserAuditLog.objects
        .values('action')
        .annotate(count=models.Count('id'))
    )

    # Get counts by day for the last 30 days
    from django.utils import timezone
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    daily_counts = (
        UserAuditLog.objects
        .filter(timestamp__gte=thirty_days_ago)
        .extra({'date': "date(timestamp)"})
        .values('date')
        .annotate(count=models.Count('id'))
        .order_by('date')
    )

    return {
        "total_logs": UserAuditLog.objects.count(),
        "action_counts": {item['action']: item['count'] for item in action_counts},
        "daily_counts": {str(item['date']): item['count'] for item in daily_counts},
        "unique_users": UserAuditLog.objects.values('user').distinct().count(),
        "unique_ips": UserAuditLog.objects.values('ip_address').distinct().count()
    }

# JWT endpoints are automatically added by ninja_jwt 