from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired
from flask_wtf import FlaskForm

class ScheduleForm(FlaskForm):
    schedule = TextAreaField("Schedule", validators = [DataRequired()])
    submit = SubmitField("Preview Schedule")