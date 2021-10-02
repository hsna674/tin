from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("", views.index_view, name="index"),
    path("add/", views.create_view, name="create"),
    path("<int:course_id>", views.show_view, name="show"),
    path("<int:course_id>/edit", views.edit_view, name="edit"),
    path("<int:course_id>/students", views.students_view, name="students"),
    path("<int:course_id>/import", views.import_students_view, name="import"),
    path("<int:course_id>/add_period", views.add_period_view, name="add_period"),
    path("<int:course_id>/edit_period", views.edit_period_view, name="edit_period"),
]
