from django.core.exceptions import ValidationError
import re

class ComplexPasswordValidator:
    """
    Validate that the password meets the following criteria:
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    - Minimum length of 8 characters
    """
    
    def __init__(self):
        self.password_regex = re.compile(
            r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
        )
    
    def validate(self, password, user=None):
        if not self.password_regex.match(password):
            raise ValidationError(
                "Password must contain at least: "
                "8 characters, one uppercase letter, "
                "one lowercase letter, one number, "
                "and one special character (@$!%*?&)."
            )
    
    def get_help_text(self):
        return (
            "Your password must contain at least 8 characters, "
            "including uppercase and lowercase letters, "
            "numbers, and special characters (@$!%*?&)."
        ) 