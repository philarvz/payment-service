from django.urls import path
from .views import ProcessPaymentView

urlpatterns = [
    path('process/', ProcessPaymentView.as_view(), name='process-payment'),
]
