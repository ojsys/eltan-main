from django.urls import path

from . import views

app_name = 'portfolio'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('add/', views.add, name='add'),
    path('<int:pk>/edit/', views.edit, name='edit'),
    path('<int:pk>/delete/', views.delete, name='delete'),
    path('<int:pk>/evidence/', views.evidence, name='evidence'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/sharing/', views.sharing, name='sharing'),
    path('report.pdf', views.report, name='report'),
    path('share/<str:token>/', views.shared, name='shared'),
]
