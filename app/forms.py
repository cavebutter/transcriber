from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SelectField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, NumberRange
from wtforms import ValidationError
from app.models import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    password2 = PasswordField('Repeat Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data.lower()).first()
        if user is not None:
            raise ValidationError('Email already registered. Please use a different email.')

class AudioUploadForm(FlaskForm):
    audio_file = FileField('Audio File', validators=[
        FileRequired(),
        FileAllowed(['wav', 'mp3', 'm4a', 'mp4', 'flac', 'ogg'], 'Invalid audio format!')
    ])
    title = StringField('Meeting Title', validators=[Optional(), Length(max=200)])
    whisper_model = SelectField('Whisper Model',
        choices=[
            ('tiny', 'Tiny (fastest, least accurate)'),
            ('base', 'Base'),
            ('small', 'Small'),
            ('medium', 'Medium'),
            ('large', 'Large (slowest, most accurate)')
        ],
        default='large'
    )
    summarizer_model = SelectField('Summarizer Model',
        choices=[
            ('qwen3-summarizer:14b', 'Qwen3 14B (faster)'),
            ('qwen3-summarizer:30b', 'Qwen3 30B (more detailed)')
        ],
        default='qwen3-summarizer:14b'
    )
    enable_diarization = BooleanField('Enable Speaker Diarization', default=True)
    min_speakers = IntegerField('Minimum Speakers', validators=[
        Optional(),
        NumberRange(min=1, max=20, message='Must be between 1 and 20')
    ])
    max_speakers = IntegerField('Maximum Speakers', validators=[
        Optional(),
        NumberRange(min=1, max=20, message='Must be between 1 and 20')
    ])
    output_format = SelectField('Output Format',
        choices=[
            ('pdf', 'PDF'),
            ('html', 'HTML'),
            ('md', 'Markdown')
        ],
        default='pdf'
    )

    def validate_min_speakers(self, min_speakers):
        if min_speakers.data and self.max_speakers.data:
            if min_speakers.data > self.max_speakers.data:
                raise ValidationError('Minimum speakers cannot be greater than maximum speakers.')

class TranscriptUploadForm(FlaskForm):
    transcript_file = FileField('Transcript File', validators=[
        FileRequired(),
        FileAllowed(['txt', 'docx'], 'Only .txt and .docx files are allowed!')
    ])
    title = StringField('Meeting Title', validators=[Optional(), Length(max=200)])
    summarizer_model = SelectField('Summarizer Model',
        choices=[
            ('qwen3-summarizer:14b', 'Qwen3 14B (faster)'),
            ('qwen3-summarizer:30b', 'Qwen3 30B (more detailed)')
        ],
        default='qwen3-summarizer:14b'
    )
    output_format = SelectField('Output Format',
        choices=[
            ('pdf', 'PDF'),
            ('html', 'HTML'),
            ('md', 'Markdown')
        ],
        default='pdf'
    )

class PasswordResetRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])

class PasswordResetForm(FlaskForm):
    password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    password2 = PasswordField('Repeat Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])