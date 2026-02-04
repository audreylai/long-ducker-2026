from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, StringField
from wtforms.fields import DecimalField
from wtforms.validators import DataRequired, Email, Length, NumberRange


class LionBidForm(FlaskForm):
    lion_slug = HiddenField(validators=[DataRequired()])
    amount = DecimalField(
        "Bid amount",
        places=2,
        rounding=None,
        validators=[DataRequired(), NumberRange(min=Decimal("0.01"), message="Enter a valid amount")],
    )
    name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField("Mobile", validators=[DataRequired(), Length(max=32)])
    agree = BooleanField(
        "I agree to the terms and conditions. If my bid wins, I commit to completing the purchase.",
        validators=[DataRequired(message="You must agree to continue.")],
    )
