from django.conf import settings
from django.urls import path

from tapir.utils import views_data_import

app_name = "utils"
urlpatterns = [
    path("data_import", views_data_import.DataImportView.as_view(), name="data_import"),
    path(
        "data_import/apply",
        views_data_import.DataImportApplyView.as_view(),
        name="data_import_apply",
    ),
    path(
        "data_import/activation",
        views_data_import.DataImportActivationView.as_view(),
        name="data_import_activation",
    ),
    path(
        "data_import/template/<str:import_type>",
        views_data_import.DataImportTemplateView.as_view(),
        name="data_import_template",
    ),
]
# The test data views need factory_boy, which only debug instances have installed
if settings.DEBUG:
    from tapir.utils import views

    urlpatterns += [
        path(
            "reset_test_data",
            views.ResetTestData.as_view(),
            name="reset_test_data",
        ),
    ]
