from django.urls import path
from . import views

app_name = 'leagues'

urlpatterns = [
    # ... existing URL patterns ...
    path('<int:pk>/dashboard/', views.LeagueDashboardView.as_view(), name='dashboard'),
] 