from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Pagination
class PaginatedResponse(BaseModel):
    # shared by every paginated list below, each subclass adds that page's items under its own key
    total: int # matching rows across every page, not just this one
    skip: int
    limit: int
    has_more: bool # true when another page exists after this one

# letters, digits, _ and - only: usernames end up in frontend urls
USERNAME_PATTERN = r"^[A-Za-z0-9_-]+$"

class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50, pattern=USERNAME_PATTERN)
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(min_length=8)

class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    image_file: str | None
    image_path: str # read from the User.image_path property

class UserPrivate(UserPublic):
    email: EmailStr

class UserUpdate(BaseModel):
    # password isn't here, it's changed through PATCH /me/password (ChangePasswordRequest)
    username: str | None = Field(default=None, min_length=1, max_length=50, pattern=USERNAME_PATTERN)
    email: EmailStr | None = Field(default=None)
    current_password: str | None = Field(default=None) # required to change email

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8) # same rule as UserCreate.password

class Token(BaseModel):
    access_token: str
    token_type: str

# Password reset
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str # the token from the emailed link's ?token= query param
    new_password: str = Field(min_length=8) # same rule as UserCreate.password

class MessageResponse(BaseModel):
    message: str

# Admin
class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    email: EmailStr
    is_admin: bool

class PaginatedAdminUsersResponse(PaginatedResponse):
    users: list[AdminUserResponse]
