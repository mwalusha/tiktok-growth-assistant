from django import forms

from .models import ContentIdea


class ContentIdeaForm(forms.ModelForm):
    class Meta:
        model = ContentIdea

        fields = [
            "title",
            "category",
            "hook",
            "script",
            "caption",
            "hashtags",
            "planned_date",
            "status",
            "notes",
        ]

        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "Example: 3 common Python assignment mistakes",
                }
            ),
            "hook": forms.TextInput(
                attrs={
                    "placeholder": "Example: Most students lose marks because of this mistake...",
                }
            ),
            "script": forms.Textarea(
                attrs={
                    "rows": 7,
                    "placeholder": "Write the main points or full video script...",
                }
            ),
            "caption": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Write the TikTok caption...",
                }
            ),
            "hashtags": forms.TextInput(
                attrs={
                    "placeholder": "#Programming #StudentTips #Python",
                }
            ),
            "planned_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Private planning notes...",
                }
            ),
        }