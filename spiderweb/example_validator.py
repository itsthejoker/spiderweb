from pydantic import EmailStr

from spiderweb.middleware.pydantic import RequestModel


class CommentForm(RequestModel):
    email: EmailStr
    comment: str
