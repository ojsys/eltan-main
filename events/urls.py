from django.urls import path

from . import views

app_name = 'events'

urlpatterns = [
    path('<int:pk>/', views.event_detail, name='detail'),
    path('<int:pk>/register/', views.register, name='register'),
    path('<int:pk>/resend-link/', views.resend_link, name='resend_link'),
    path('payment/return/', views.payment_return, name='payment_return'),
    path('r/<str:token>/', views.registration_page, name='registration'),
    path('r/<str:token>/pay/', views.pay, name='pay'),
    path('r/<str:token>/activity/', views.submit_activity, name='submit_activity'),
    path('r/<str:token>/certificate/', views.download_certificate, name='download_certificate'),
    path('certificates/verify/<str:certificate_id>/', views.verify_certificate, name='verify_certificate'),
]
