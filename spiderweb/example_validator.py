from pydantic import EmailStr

from spiderweb.middleware.pydantic import SpiderwebModel


class CommentForm(SpiderwebModel):
    email: EmailStr
    comment: str
