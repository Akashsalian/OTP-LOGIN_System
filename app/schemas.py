from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
import re

class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    @field_validator("email")
    @classmethod
    def normalise_email(cls, value):
        return str(value).strip().lower()

class RegisterRequest(EmailRequest):
    name: str = Field(min_length=2, max_length=100)
    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = " ".join(value.split())
        if not value:
            raise ValueError("Enter your full name.")
        if not re.fullmatch(r"[^\W\d_]+(?:[ '\u2019-][^\W\d_]+)*", value, flags=re.UNICODE):
            raise ValueError("Your name can only contain letters, spaces, apostrophes, and hyphens.")
        return value

class OtpRequest(EmailRequest):
    pass

class VerifyOtpRequest(EmailRequest):
    otp: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")
