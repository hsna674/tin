import csv
import datetime
import json
import logging
import os
import subprocess
import zipfile
from io import BytesIO

from django import http
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.utils.timezone import now

from ... import sandboxing
from ..auth.decorators import login_required, teacher_or_superuser_required
from ..courses.models import Course, Period
from ..submissions.models import Submission
from ..submissions.tasks import run_submission
from ..users.models import User
from .forms import (
    AssignmentForm,
    FileSubmissionForm,
    FolderForm,
    GraderScriptUploadForm,
    FileUploadForm,
    TextSubmissionForm,
)
from .models import Assignment, CooldownPeriod, LogMessage, Quiz

logger = logging.getLogger(__name__)


@login_required
def show_view(request, assignment_id):
    """
    Shows an overview of the assignment
    :param request: The request
    :param assignment_id: The assignment id
    """
    assignment = get_object_or_404(
        Assignment.objects.filter_visible(request.user), id=assignment_id
    )
    course = assignment.course
    quiz_accessible = assignment.is_quiz and assignment.quiz.open_for_student(request.user)

    if course.is_only_student_in_course(request.user):
        submissions = Submission.objects.filter(
            student=request.user, assignment=assignment
        ).order_by("-date_submitted")
        latest_submission = submissions.first() if submissions else None

        return render(
            request,
            "assignments/show.html",
            {
                "course": assignment.course,
                "folder": assignment.folder,
                "assignment": assignment,
                "submissions": submissions,
                "latest_submission": latest_submission,
                "is_student": course.is_student_in_course(request.user),
                "is_teacher": request.user in course.teacher.all(),
                "quiz_accessible": quiz_accessible,
            },
        )
    else:
        students_and_submissions = []
        new_since_last_login = None
        new_in_last_24 = None
        teacher_last_login = request.user.last_login
        time_24_hours_ago = now() - datetime.timedelta(days=1)

        period = request.GET.get("period", "")
        period_set = course.period_set.order_by("teacher", "name")

        if course.period_set.exists():
            if period == "":
                if request.user in course.teacher.all():
                    try:
                        period = course.period_set.filter(teacher=request.user).order_by("name")[0].id
                    except:
                        period = "all"
                else:
                    period = "all"
            
            if period == "all":
                active_period = "all"
                student_list = course.students.all().order_by("periods", "last_name")
            else:
                active_period = get_object_or_404(Period.objects.filter(course=course), id=int(period))
                student_list = active_period.students.all().order_by("last_name")
        else:
            active_period = "all"
            student_list = course.students.all().order_by("periods", "last_name")

        for student in student_list:
            period = student.periods.filter(course=assignment.course)
            latest_submission = (
                Submission.objects.filter(student=student, assignment=assignment)
                .order_by("-date_submitted")
                .first()
            )

            if not assignment.is_quiz:
                if latest_submission:
                    new_since_last_login = latest_submission.date_submitted > teacher_last_login
                    new_in_last_24 = latest_submission.date_submitted > time_24_hours_ago
                students_and_submissions.append(
                    (student, period, latest_submission, new_since_last_login, new_in_last_24)
                )
            else:
                students_and_submissions.append(
                    (student, period, latest_submission, assignment.quiz.ended_for_student(student), assignment.quiz.locked_for_student(student))
                )

        context = {
            "course": course,
            "folder": assignment.folder,
            "assignment": assignment,
            "students_and_submissions": students_and_submissions,
            "log_file_exists": (
                assignment.grader_log_filename is not None
                and os.path.exists(
                    os.path.join(settings.MEDIA_ROOT, assignment.grader_log_filename)
                )
            ),
            "is_student": course.is_student_in_course(request.user),
            "is_teacher": request.user in course.teacher.all(),
            "period_set": period_set,
            "active_period": active_period,
            "quiz_accessible": quiz_accessible,
        }

        submissions = Submission.objects.filter(
            student=request.user, assignment=assignment
        ).order_by("-date_submitted")
        latest_submission = submissions.first() if submissions else None
        context.update({"submissions": submissions, "latest_submission": latest_submission})

        return render(request, "assignments/show.html", context)


@teacher_or_superuser_required
def create_view(request, course_id):
    """Creates an assignment"""
    course = get_object_or_404(Course.objects.filter_editable(request.user), id=course_id)

    if request.method == "POST":
        assignment_form = AssignmentForm(course, request.POST)
        if assignment_form.is_valid():
            assignment = assignment_form.save(commit=False)
            assignment.course = course
            assignment.save()

            quiz_type = assignment_form.cleaned_data["is_quiz"]
            if quiz_type != "-1":
                Quiz.objects.create(
                    assignment = assignment,
                    action = quiz_type
                )
            
            return redirect("assignments:show", assignment.id)
    else:
        assignment_form = AssignmentForm(course)
    return render(
        request,
        "assignments/edit_create.html",
        {
            "assignment_form": assignment_form,
            "course": course,
            "action": "add",
            "nav_item": "Create assignment",
        },
    )


@teacher_or_superuser_required
def edit_view(request, assignment_id):
    """Edits an assignment"""
    assignment = get_object_or_404(
        Assignment.objects.filter_editable(request.user), id=assignment_id
    )

    course = assignment.course
    initial_is_quiz = -1
    try:
        initial_is_quiz = assignment.quiz.action
    except:
        pass
    assignment_form = AssignmentForm(course, instance=assignment, initial={"is_quiz": initial_is_quiz})
    if request.method == "POST":
        assignment_form = AssignmentForm(course, data=request.POST, instance=assignment)
        if assignment_form.is_valid():
            assignment_form.save()

            quiz_type = assignment_form.cleaned_data["is_quiz"]
            if quiz_type == "-1":
                try:
                    assignment.quiz.delete()
                except:
                    pass
            else:
                try:
                    assignment.quiz.action = quiz_type
                    assignment.save()
                    assignment.quiz.save()
                except:
                    Quiz.objects.create(
                        assignment = assignment,
                        action = quiz_type
                    )

            return redirect("assignments:show", assignment.id)

    return render(
        request,
        "assignments/edit_create.html",
        {
            "assignment_form": assignment_form,
            "course": assignment.course,
            "folder": assignment.folder,
            "assignment": assignment,
            "action": "edit",
            "nav_item": "Edit",
        },
    )


@teacher_or_superuser_required
def delete_view(request, assignment_id):
    """Deletes an assignment"""
    assignment = get_object_or_404(
        Assignment.objects.filter_editable(request.user), id=assignment_id
    )
    course = assignment.course
    folder = assignment.folder
    assignment.delete()
    if folder:
        return redirect(reverse("assignments:show_folder", args=(course.id, folder.id)))
    return redirect(reverse("courses:show", args=(course.id,)))


@teacher_or_superuser_required
def upload_grader_view(request, assignment_id):
    """Uploads a grader for an assignment"""
    assignment = get_object_or_404(
        Assignment.objects.filter_editable(request.user), id=assignment_id
    )

    grader_form = GraderScriptUploadForm()

    grader_file_errors = ""

    if request.method == "POST":
        if request.FILES.get("grader_file"):
            if request.FILES["grader_file"].size <= settings.SUBMISSION_SIZE_LIMIT:
                grader_form = GraderScriptUploadForm(
                    request.POST,
                    request.FILES,
                )
                if grader_form.is_valid():
                    try:
                        grader_text = request.FILES["grader_file"].read().decode()
                    except UnicodeDecodeError:
                        grader_file_errors = "Please don't upload binary files."
                    else:
                        assignment.save_grader_file(grader_text)

                        return redirect("assignments:show", assignment.id)
                else:
                    grader_file_errors = grader_form.errors
            else:
                grader_file_errors = "That file's too large. Are you sure it's a Python program?"
        else:
            grader_file_errors = "Please select a file."

    return render(
        request,
        "assignments/upload_grader.html",
        {
            "grader_form": grader_form,
            "grader_file_errors": grader_file_errors,
            "course": assignment.course,
            "folder": assignment.folder,
            "assignment": assignment,
            "nav_item": "Upload grader",
        },
    )


@teacher_or_superuser_required
def student_submissions_view(request, assignment_id, student_id):
    assignment = get_object_or_404(
        Assignment.objects.filter_editable(request.user), id=assignment_id
    )
    student = get_object_or_404(User, id=student_id)

    submissions = Submission.objects.filter(student=student, assignment=assignment).order_by(
        "-date_submitted"
    )
    latest_submission = submissions.first() if submissions else None

    log_messages = assignment.quiz.log_messages.filter(student=request.user).order_by("date") if assignment.is_quiz else None

    latest_submission_text = None
    if latest_submission:
        with open(latest_submission.backup_file_path, "r", encoding="utf-8") as f_obj:
            latest_submission_text = f_obj.read()

    return render(
        request,
        "assignments/student_submissions.html",
        {
            "course": assignment.course,
            "folder": assignment.folder,
            "assignment": assignment,
            "student": student,
            "submissions": submissions,
            "latest_submission": latest_submission,
            "latest_submission_text": latest_submission_text,
            "log_messages": log_messages,
        },
    )


@login_required
def submit_view(request, assignment_id):
    assignment = get_object_or_404(
        Assignment.objects.filter_visible(request.user), id=assignment_id
    )

    if assignment.is_quiz:
        raise http.Http404

    student = request.user

    submissions = Submission.objects.filter(student=student, assignment=assignment).order_by(
        "-date_submitted"
    )
    latest_submission = submissions.first() if submissions else None
    latest_submission_text = None
    if latest_submission:
        with open(latest_submission.backup_file_path, "r", encoding="utf-8") as f_obj:
            latest_submission_text = f_obj.read()

    file_form = FileSubmissionForm()
    text_form = TextSubmissionForm(initial={"text": latest_submission_text})

    file_errors = ""
    text_errors = ""

    if request.method == "POST":
        if assignment.grader_file is None:
            return redirect("assignments:show", assignment.id)

        if (
            Submission.objects.filter(student=request.user, complete=False).count()
            >= settings.CONCURRENT_USER_SUBMISSION_LIMIT
        ):
            if request.FILES.get("file"):
                file_form = FileSubmissionForm(request.POST, request.FILES)
                file_errors = (
                    "You may only have a maximum of {} submission{} running at the same "
                    "time".format(
                        settings.CONCURRENT_USER_SUBMISSION_LIMIT,
                        "" if settings.CONCURRENT_USER_SUBMISSION_LIMIT == 1 else "s",
                    )
                )
            else:
                text_form = TextSubmissionForm(request.POST)
                text_errors = (
                    "You may only have a maximum of {} submission{} running at the same "
                    "time".format(
                        settings.CONCURRENT_USER_SUBMISSION_LIMIT,
                        "" if settings.CONCURRENT_USER_SUBMISSION_LIMIT == 1 else "s",
                    )
                )
        elif CooldownPeriod.exists(assignment=assignment, student=student):
            cooldown_period = CooldownPeriod.objects.get(assignment=assignment, student=student)

            end_delta = cooldown_period.get_time_to_end()
            # Throw out the microseconds
            end_delta = datetime.timedelta(days=end_delta.days, seconds=end_delta.seconds)

            if request.FILES.get("file"):
                file_form = FileSubmissionForm(request.POST, request.FILES)
                file_errors = (
                    "You have made too many submissions too quickly. You will be able to re-submit"
                    "in {}.".format(end_delta)
                )
            else:
                text_form = TextSubmissionForm(request.POST)
                text_errors = (
                    "You have made too many submissions too quickly. You will be able to re-submit"
                    "in {}.".format(end_delta)
                )
        else:
            if request.FILES.get("file"):
                if request.FILES["file"].size <= settings.SUBMISSION_SIZE_LIMIT:
                    file_form = FileSubmissionForm(request.POST, request.FILES)
                    if file_form.is_valid():
                        try:
                            submission_text = request.FILES["file"].read().decode()
                        except UnicodeDecodeError:
                            file_errors = "Please don't upload binary files."
                        else:
                            submission = Submission()
                            submission.assignment = assignment
                            submission.student = student
                            submission.save_file(submission_text)
                            submission.save()

                            assignment.check_rate_limit(student)

                            submission.create_backup_copy(submission_text)

                            run_submission.delay(submission.id)
                            return redirect("assignments:show", assignment.id)
                else:
                    file_errors = "That file's too large. Are you sure it's a Python program?"
            else:
                text_form = TextSubmissionForm(request.POST)
                if text_form.is_valid():
                    submission_text = text_form.cleaned_data["text"]
                    if len(submission_text) <= settings.SUBMISSION_SIZE_LIMIT:
                        submission = text_form.save(commit=False)
                        submission.assignment = assignment
                        submission.student = student
                        submission.save_file(submission_text)
                        submission.save()

                        assignment.check_rate_limit(student)

                        submission.create_backup_copy(submission_text)

                        run_submission.delay(submission.id)
                        return redirect("assignments:show", assignment.id)
                    else:
                        text_errors = "Submission too large"

    return render(
        request,
        "assignments/submit.html",
        {
            "file_form": file_form,
            "text_form": text_form,
            "file_errors": file_errors,
            "text_errors": text_errors,
            "course": assignment.course,
            "folder": assignment.folder,
            "assignment": assignment,
            "nav_item": "Submit",
        },
    )


@teacher_or_superuser_required
def scores_csv_view(request, assignment_id):
    assignment = get_object_or_404(
        Assignment.objects.filter_editable(request.user), id=assignment_id
    )

    response = http.HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="scores.csv"'

    writer = csv.writer(response)
    writer.writerow(["Name", "Username", "Period", "Raw Score", "Formatted Grade"])

    for student in assignment.course.students.all().order_by("periods", "last_name"):
        row = []
        row.append(student.full_name)
        row.append(student.username)
        periods = ", ".join([p.name for p in student.periods.filter(course=assignment.course)])
        row.append(periods)
        latest_submission = (
            Submission.objects.filter(student=student, assignment=assignment)
            .order_by("-date_submitted")
            .first()
        )
        if latest_submission is not None:
            if latest_submission.points_received:
                row.append(latest_submission.points_received)
                row.append(latest_submission.formatted_grade)
            else:
                row.append("NG")
                row.append("NG")
        else:
            row.append("M")
            row.append("M")
        writer.writerow(row)

    return response


@teacher_or_superuser_required
def download_submissions_view(request, assignment_id):
    assignment = get_object_or_404(
        Assignment.objects.filter_editable(request.user), id=assignment_id
    )
    name = "assignment_{}_student_submissions.zip".format(assignment.id)

    s = BytesIO()
    zf = zipfile.ZipFile(s, "w")
    for student in assignment.course.students.all():
        latest_submission = (
            Submission.objects.filter(student=student, assignment=assignment)
            .order_by("-date_submitted")
            .first()
        )
        if latest_submission is not None:
            zf.write(latest_submission.file.path, arcname="{}.py".format(student.username))
    zf.close()
    resp = http.HttpResponse(s.getvalue(), content_type="application/x-zip-compressed")
    resp["Content-Disposition"] = "attachment; filename={}".format(name)
    return resp


@teacher_or_superuser_required
def download_log_view(request, assignment_id):
    assignment = get_object_or_404(
        Assignment.objects.filter_editable(request.user), id=assignment_id
    )

    log_file_name = os.path.join(settings.MEDIA_ROOT, assignment.grader_log_filename)

    if (
        request.user not in assignment.course.teacher.all() and not request.user.is_superuser
    ) or not os.path.exists(log_file_name):
        raise http.Http404

    assigment_dir = os.path.dirname(log_file_name)

    args = sandboxing.get_assignment_sandbox_args(
        ["cat", "--", log_file_name],
        network_access=False,
        whitelist=[assigment_dir],
        read_only=[assigment_dir],
    )

    try:
        res = subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True,
        )
    except FileNotFoundError as e:
        logger.error("Cannot run processes: %s", e)
        raise FileNotFoundError from e

    data = res.stdout

    response = http.HttpResponse(data, content_type="text/plain")
    response["Content-Disposition"] = 'attachment; filename="{}-grader.log"'.format(
        slugify(assignment.name)
    )

    return response


@teacher_or_superuser_required
def create_folder_view(request, course_id):
    course = get_object_or_404(Course.objects.filter_editable(request.user), id=course_id)

    form = FolderForm()
    if request.method == "POST":
        form = FolderForm(request.POST)
        if form.is_valid():
            folder = form.save(commit=False)
            folder.course = course
            folder.save()
            return redirect("courses:show", course.id)

    context = {
        "form": form,
        "nav_item": "Create folder",
        "course": course,
        "action": "add",
    }

    return render(request, "assignments/edit_create_folder.html", context=context)


@teacher_or_superuser_required
def edit_folder_view(request, course_id, folder_id):
    course = get_object_or_404(Course.objects.filter_editable(request.user), id=course_id)
    folder = get_object_or_404(course.folders.all(), id=folder_id)

    form = FolderForm(instance=folder)
    if request.method == "POST":
        form = FolderForm(request.POST, instance=folder)
        if form.is_valid():
            form.save()
            return redirect("assignments:show_folder", course.id, folder.id)

    context = {
        "form": form,
        "nav_item": "Edit",
        "course": course,
        "folder": folder,
        "action": "edit",
    }

    return render(request, "assignments/edit_create_folder.html", context=context)


@teacher_or_superuser_required
def delete_folder_view(request, course_id, folder_id):
    course = get_object_or_404(Course.objects.filter_editable(request.user), id=course_id)
    folder = get_object_or_404(course.folders.all(), id=folder_id)

    folder.delete()
    return redirect("courses:show", course.id)


@login_required
def show_folder_view(request, course_id, folder_id):
    course = get_object_or_404(Course.objects.filter_visible(request.user), id=course_id)
    folder = get_object_or_404(course.folders.all(), id=folder_id)

    assignments = course.assignments.filter(folder=folder).filter_visible(request.user)
    if course.sort_assignments_by == "due_date":
        assignments = assignments.order_by("-due")
    elif course.sort_assignments_by == "name":
        assignments = assignments.order_by("name")

    context = {
        "course": course,
        "folder": folder,
        "assignments": assignments,
        "period": course.period_set.filter(students=request.user),
        "is_student": course.is_student_in_course(request.user),
        "is_teacher": request.user in course.teacher.all(),
    }
    if course.is_student_in_course(request.user):
        context["unsubmitted_assignments"] = assignments.exclude(submissions__student=request.user)

    return render(request, "assignments/show_folder.html", context=context)


@teacher_or_superuser_required
def upload_file_view(request, assignment_id):
    assignment = get_object_or_404(
        Assignment.objects.filter_editable(request.user), id=assignment_id
    )

    form = FileUploadForm()

    file_errors = ""

    if request.method == "POST":
        if request.FILES.get("upload_file"):
            if request.FILES["upload_file"].size <= settings.SUBMISSION_SIZE_LIMIT:
                form = FileUploadForm(
                    request.POST,
                    request.FILES,
                )
                if form.is_valid():
                    try:
                        text = request.FILES["upload_file"].read().decode()
                    except UnicodeDecodeError:
                        file_errors = "Please don't upload binary files."
                    else:
                        assignment.save_file(text, request.FILES["upload_file"].name)

                        return redirect("courses:index")
                else:
                    file_errors = form.errors
            else:
                file_errors = "That file's too large."
        else:
            file_errors = "Please select a file."

    return render(
        request,
        "assignments/upload_file.html",
        {
            "form": form,
            "file_errors": file_errors,
            "course": assignment.course,
            "folder": assignment.folder,
            "assignment": assignment,
            "nav_item": "Upload file",
        },
    )


@login_required
def quiz_view(request, assignment_id):
    assignment = get_object_or_404(Assignment.objects.filter_visible(request.user), id=assignment_id)

    if not assignment.is_quiz or assignment.quiz.locked_for_student(request.user) or assignment.quiz.ended_for_student(request.user):
        raise http.Http404

    student = request.user

    submissions = Submission.objects.filter(student=student, assignment=assignment).order_by("-date_submitted")
    latest_submission = submissions.first() if submissions else None

    latest_submission_text = None
    if latest_submission:
        with open(latest_submission.backup_file_path, "r", encoding="utf-8") as f_obj:
            latest_submission_text = f_obj.read()

    text_form = TextSubmissionForm(initial={"text": latest_submission_text})
    text_errors = ""

    if request.method == "POST":
        if assignment.grader_file is None:
            return redirect("assignments:show", assignment.id)

        if Submission.objects.filter(student=request.user, complete=False).count() >= settings.CONCURRENT_USER_SUBMISSION_LIMIT:
            text_form = TextSubmissionForm(request.POST)
            text_errors = (
                "You may only have a maximum of {} submission{} running at the same "
                "time".format(
                    settings.CONCURRENT_USER_SUBMISSION_LIMIT,
                    "" if settings.CONCURRENT_USER_SUBMISSION_LIMIT == 1 else "s",
                )
            )
        elif CooldownPeriod.exists(assignment=assignment, student=student):
            cooldown_period = CooldownPeriod.objects.get(assignment=assignment, student=student)

            end_delta = cooldown_period.get_time_to_end()
            # Throw out the microseconds
            end_delta = datetime.timedelta(days=end_delta.days, seconds=end_delta.seconds)

            text_form = TextSubmissionForm(request.POST)
            text_errors = (
                "You have made too many submissions too quickly. You will be able to re-submit"
                "in {}.".format(end_delta)
            )
        else:
            text_form = TextSubmissionForm(request.POST)
            if text_form.is_valid():
                submission_text = text_form.cleaned_data["text"]
                if len(submission_text) <= settings.SUBMISSION_SIZE_LIMIT:
                    submission = text_form.save(commit=False)
                    submission.assignment = assignment
                    submission.student = student
                    submission.save_file(submission_text)
                    submission.save()

                    assignment.check_rate_limit(student)

                    submission.create_backup_copy(submission_text)

                    run_submission.delay(submission.id)
                    return redirect("assignments:quiz", assignment.id)
                else:
                    text_errors = "Submission too large"

    quiz_color = assignment.quiz.issues_for_student(request.user) and assignment.quiz.action == "1"

    return render(
        request,
        "assignments/quiz.html",
        {
            "nav_item": "Take Quiz",
            "course": assignment.course,
            "folder": assignment.folder,
            "assignment": assignment,
            "latest_submission": latest_submission,
            "text_form": text_form,
            "text_errors": text_errors,
            "quiz_color": quiz_color,
        },
    )


@login_required
def report_view(request, assignment_id):
    assignment = get_object_or_404(Assignment.objects.filter_visible(request.user), id=assignment_id)

    content = request.GET.get("content", "")
    severity = int(request.GET.get("severity", 0))

    if assignment.quiz.ended_for_student(request.user):
        json_data = json.dumps("no action")
    else:
        LogMessage.objects.create(
            quiz=assignment.quiz,
            student=request.user,
            content=content,
            severity=severity
        )

        resp = "no action"
        if severity >= settings.QUIZ_ISSUE_THRESHOLD:
            if assignment.quiz.action == "1":
                resp = "color"
            elif assignment.quiz.action == "2":
                resp = "lock"

        json_data = json.dumps(resp)
    return http.HttpResponse(json_data, content_type="application/json")


@login_required
def quiz_end_view(request, assignment_id):
    assignment = get_object_or_404(Assignment.objects.filter_visible(request.user), id=assignment_id)

    LogMessage.objects.create(
        quiz=assignment.quiz,
        student=request.user,
        content="Ended quiz",
        severity=0
    )

    return redirect("assignments:show", assignment.id)


@teacher_or_superuser_required
def clear_view(request, assignment_id, user_id):
    assignment = get_object_or_404(Assignment.objects.filter_editable(request.user), id=assignment_id)
    user = get_object_or_404(get_user_model(), id=user_id)

    assignment.quiz.log_messages.filter(student=user).delete()

    return redirect("assignments:student_submission", assignment.id, user.id)
