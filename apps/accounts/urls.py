from django.urls import path

from .views import SmtpCredentialView

urlpatterns = [
    path("smtp/", SmtpCredentialView.as_view(), name="account-smtp"),
]
