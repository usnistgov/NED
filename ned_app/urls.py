from django.urls import path
from ned_app import views

urlpatterns = [
    path('', views.home, name='home'),
]
