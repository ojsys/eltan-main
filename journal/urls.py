from django.urls import path

from . import editor_views, review_views, views

app_name = 'journal'

urlpatterns = [
    # Public journal
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('editorial-board/', views.editorial_board, name='editorial_board'),
    path('author-guidelines/', views.guidelines, name='guidelines'),
    path('policies/', views.policies, name='policies'),
    path('issues/', views.issue_list, name='issue_list'),
    path('issues/<slug:slug>/', views.issue_detail, name='issue_detail'),
    path('articles/<slug:slug>/', views.article_detail, name='article_detail'),
    path('articles/<slug:slug>/pdf/', views.article_pdf, name='article_pdf'),
    path('search/', views.search, name='search'),

    # Authors
    path('submit/', views.submit, name='submit'),
    path('my-submissions/', views.my_submissions, name='my_submissions'),
    path('submissions/<int:pk>/', views.submission_detail, name='submission_detail'),
    path('submissions/<int:pk>/revise/', views.upload_revision, name='upload_revision'),
    path('submissions/<int:pk>/withdraw/', views.withdraw_submission, name='withdraw_submission'),
    path('submissions/<int:pk>/pay/', views.pay_apc, name='pay_apc'),
    path('apc/success/', views.apc_success, name='apc_success'),
    path('files/<int:pk>/', views.submission_file, name='submission_file'),

    # Reviewers — everything runs off the token in the invitation email
    path('review/<str:token>/', review_views.review, name='review'),
    path('review/<str:token>/respond/', review_views.review_respond, name='review_respond'),
    path('review/<str:token>/file/<int:pk>/', review_views.review_file, name='review_file'),

    # Editorial office
    path('editor/', editor_views.dashboard, name='editor_dashboard'),
    path('editor/submissions/<int:pk>/', editor_views.submission, name='editor_submission'),
    path('editor/submissions/<int:pk>/assign/', editor_views.assign_editor, name='assign_editor'),
    path('editor/submissions/<int:pk>/invite/', editor_views.invite_reviewer, name='invite_reviewer'),
    path('editor/submissions/<int:pk>/decide/', editor_views.record_decision, name='record_decision'),
    path('editor/submissions/<int:pk>/waive-apc/', editor_views.waive_apc, name='waive_apc'),
    path('editor/submissions/<int:pk>/publish/', editor_views.publish, name='publish'),
    path('editor/reviews/<int:pk>/resend/', editor_views.resend_invitation, name='resend_invitation'),
    path('editor/reviews/<int:pk>/remind/', editor_views.remind_reviewer, name='remind_reviewer'),
    path('editor/reviews/<int:pk>/cancel/', editor_views.cancel_review, name='cancel_review'),
    path('editor/issues/', editor_views.issue_list, name='editor_issues'),
    path('editor/issues/new/', editor_views.issue_create, name='issue_create'),
    path('editor/issues/<int:pk>/', editor_views.issue_edit, name='issue_edit'),
]
