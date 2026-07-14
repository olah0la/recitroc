"""Auth schemas — the shapes exchanged during login.

TEACHING NOTE — there is no LoginRequest schema here on purpose: the login
endpoint uses OAuth2PasswordRequestForm (a *form*, not JSON) because that
is what the OAuth2 password flow specifies — and it's what makes the
"Authorize" button in the /docs UI work out of the box.
"""

from pydantic import BaseModel


class Token(BaseModel):
    """Response of POST /auth/login.

    `token_type: "bearer"` tells the client how to present the token:
    an `Authorization: Bearer <token>` header on every request.
    """

    access_token: str
    token_type: str = "bearer"
