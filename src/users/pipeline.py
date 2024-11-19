from social_core.pipeline.partial import partial
from social_core.exceptions import AuthException

def auto_merge_accounts(strategy, details, user=None, *args, **kwargs):
    """Automatically merge accounts if same email is found."""
    if not user:
        email = details.get('email')
        if email:
            existing_user = strategy.storage.user.get_users_by_email(email)
            if existing_user and len(existing_user) == 1:
                existing_user = existing_user[0]
                # Merge the accounts automatically
                social_user = kwargs.get('social').user
                existing_user.merge_account(social_user)
                return {'user': existing_user}
            elif len(existing_user) > 1:
                # Multiple accounts with same email - this is an error case
                raise AuthException(
                    strategy.backend,
                    'Multiple accounts found with this email address'
                )
    return None 