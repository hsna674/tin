from django import forms
from .models import Assignment
from ..submissions.models import Submission


class AssignmentForm(forms.ModelForm):
    due = forms.DateTimeInput()
    enable_grader_timeout = forms.BooleanField(label = "Set a timeout for the grader?")
    grader_timeout = forms.IntegerField(label = "Grader timeout (seconds):")

    def __init__(self, *args, **kwargs):
        super(AssignmentForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Assignment
        fields = ["name", "description", "points_possible", "due", "enable_grader_timeout", "grader_timeout"]

class GraderFileSubmissionForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ["grader_file"]


class FileSubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ["file"]


class TextSubmissionForm(forms.ModelForm):
    text = forms.CharField(widget = forms.Textarea(attrs = {"cols": 80, "rows": 20}))

    class Meta:
        model = Submission
        fields = []
