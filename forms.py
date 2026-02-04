from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, MultipleFileField, PasswordField, StringField, TextAreaField, IntegerField
from wtforms.fields import DecimalField, DateTimeLocalField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional


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


class AdminLoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=64)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=128)])


class AdminLionForm(FlaskForm):
    name = StringField("Lion name", validators=[DataRequired(), Length(max=120)])
    house = StringField("House", validators=[Optional(), Length(max=80)])
    summary = TextAreaField("Summary", validators=[DataRequired(), Length(max=1000)])
    current_bid = IntegerField("Current bid", validators=[Optional(), NumberRange(min=0)])
    bidding_starts_at = DateTimeLocalField("Bidding starts", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    bidding_ends_at = DateTimeLocalField("Bidding ends", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    images = MultipleFileField("Lion images", validators=[Optional()])
