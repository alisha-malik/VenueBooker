from django import forms
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta

class BookingForm(forms.Form):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True,
        error_messages={
            'required': 'Please select a start date',
            'invalid': 'Please enter a valid date in YYYY-MM-DD format'
        }
    )
    start_time = forms.TimeField(
        widget=forms.Select(choices=[]),
        required=True,
        error_messages={
            'required': 'Please select a start time',
            'invalid': 'Please select a valid time'
        }
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True,
        error_messages={
            'required': 'Please select an end date',
            'invalid': 'Please enter a valid date in YYYY-MM-DD format'
        }
    )
    end_time = forms.TimeField(
        widget=forms.Select(choices=[]),
        required=True,
        error_messages={
            'required': 'Please select an end time',
            'invalid': 'Please select a valid time'
        }
    )
    method = forms.ChoiceField(
        choices=[('Credit Card', 'Credit Card'), ('Debit Card', 'Debit Card')],
        required=True,
        error_messages={
            'required': 'Please select a payment method',
            'invalid_choice': 'Please select either Credit Card or Debit Card'
        }
    )
    card_number = forms.CharField(
        max_length=23,
        min_length=13,
        required=True,
        widget=forms.TextInput(attrs={
            'pattern': '[0-9 ]{13,23}',
            'placeholder': '1234 5678 9012 3456'
        }),
        error_messages={
            'required': 'Please enter your card number',
            'min_length': 'Card number must be at least 13 digits',
            'max_length': 'Card number cannot exceed 19 digits',
            'invalid': 'Please enter a valid card number (digits only, spaces allowed)'
        }
    )
    expiry_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'month'}),
        required=True,
        error_messages={
            'required': 'Please enter the card expiry date',
            'invalid': 'Please enter a valid expiry date in YYYY-MM format'
        }
    )
    cvv = forms.CharField(
        max_length=4,
        min_length=3,
        required=True,
        widget=forms.PasswordInput(attrs={'pattern': '[0-9]{3,4}'}),
        error_messages={
            'required': 'Please enter the CVV code',
            'min_length': 'CVV must be at least 3 digits',
            'max_length': 'CVV cannot exceed 4 digits',
            'invalid': 'Please enter a valid CVV (3 or 4 digits)'
        }
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        start_time = cleaned_data.get('start_time')
        end_date = cleaned_data.get('end_date')
        end_time = cleaned_data.get('end_time')
        expiry_date = cleaned_data.get('expiry_date')

        # Validate booking dates
        if start_date and end_date and start_time and end_time:
            start_datetime = datetime.combine(start_date, start_time)
            end_datetime = datetime.combine(end_date, end_time)
            
            # Check if booking is at least 5 days in advance
            min_booking_date = datetime.now() + timedelta(days=5)
            if start_datetime < min_booking_date:
                raise ValidationError('Booking must be made at least 5 days in advance')
            
            # Check if end time is after start time
            if end_datetime <= start_datetime:
                raise ValidationError('End time must be after start time')
            
            # Check if duration is at least 1 hour
            duration = end_datetime - start_datetime
            if duration.total_seconds() < 3600:
                raise ValidationError('Booking duration must be at least 1 hour')

        # Validate card expiry
        if expiry_date:
            current_date = datetime.now()
            current_year = current_date.year
            current_month = current_date.month
            
            expiry_year = expiry_date.year
            expiry_month = expiry_date.month
            
            if expiry_year < current_year or (expiry_year == current_year and expiry_month < current_month):
                raise ValidationError('Card has expired. Please enter a valid future expiry date')

        return cleaned_data

    def clean_card_number(self):
        card_number = self.cleaned_data['card_number']
        # Remove any non-digit characters and spaces
        card_number = ''.join(filter(str.isdigit, card_number))
        
        # More relaxed validation
        if len(card_number) < 13:
            raise ValidationError('Please enter a valid card number (at least 13 digits)')
        if len(card_number) > 19:
            raise ValidationError('Card number is too long. Please check and try again')
            
        return card_number

    def clean_cvv(self):
        cvv = self.cleaned_data['cvv']
        if not (3 <= len(cvv) <= 4):
            raise ValidationError('CVV must be 3 or 4 digits')
        return cvv 