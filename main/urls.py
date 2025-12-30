from django.urls import path
from main.views import BusinessListCreateAPIView, BusinessDetailAPIView

urlpatterns = [
    # ... your existing login/register urls ...
    
    # API Endpoints
    path('api/businesses/', BusinessListCreateAPIView.as_view(), name='business-list'),
    path('api/businesses/<int:pk>/', BusinessDetailAPIView.as_view(), name='business-detail'),
]