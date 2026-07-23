from django import forms

from .models import ContentIdea


class ContentCoachForm(forms.Form):
    niche = forms.CharField(
        max_length=160,
        label="Your content niche",
        widget=forms.TextInput(
            attrs={
                "placeholder": (
                    "Example: beginner Python tutorials for students"
                ),
            }
        ),
    )


class GeneratedIdeaSaveForm(forms.Form):
    title = forms.CharField(max_length=200)
    hook = forms.CharField(max_length=300)
    caption = forms.CharField()
    hashtags = forms.CharField(max_length=500)
    reason = forms.CharField(required=False)
    suggested_length = forms.CharField(
        max_length=100,
        required=False,
    )
    suggested_posting_time = forms.CharField(
        max_length=160,
        required=False,
    )


class ViralPredictorForm(forms.Form):
    caption = forms.CharField(
        max_length=2200,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Paste your planned caption...",
            }
        ),
    )
    hashtags = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "#Python #CreatorTips #LearnOnTikTok",
            }
        ),
    )


class ChatAssistantForm(forms.Form):
    message = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": (
                    "Ask about your growth, videos, score, trends, "
                    "or what to post next..."
                ),
            }
        ),
    )


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
            "reason",
            "suggested_length",
            "suggested_posting_time",
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
