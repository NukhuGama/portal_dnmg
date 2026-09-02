from django.urls import path
from . import views

app_name = 'cms'

urlpatterns = [
    # Public views
    path('news/', views.PublicNewsListView.as_view(), name='public_news_list'),
    path('news/<slug:slug>/', views.PublicNewsDetailView.as_view(), name='public_news_detail'),
    path('bulletins/', views.PublicBulletinListView.as_view(), name='public_bulletin_list'),
    path('bulletins/<slug:slug>/', views.PublicBulletinDetailView.as_view(), name='public_bulletin_detail'),

    # Public Career views
    path('careers/', views.PublicCareerListView.as_view(), name='public_career_list'),
    path('careers/<slug:slug>/', views.PublicCareerDetailView.as_view(), name='public_career_detail'),

    # Admin CMS views
    path('admin/news/', views.AdminNewsListView.as_view(), name='admin_news_list'),
    path('admin/news/create/', views.NewsCreateView.as_view(), name='news_create'),
    path('admin/news/<int:pk>/update/', views.NewsUpdateView.as_view(), name='news_update'),

    path('admin/bulletins/', views.AdminBulletinListView.as_view(), name='admin_bulletin_list'),
    path('admin/bulletins/create/', views.BulletinCreateView.as_view(), name='bulletin_create'),
    path('admin/bulletins/<int:pk>/update/', views.BulletinUpdateView.as_view(), name='bulletin_update'),

    # Admin Career views
    path('admin/careers/', views.AdminCareerListView.as_view(), name='admin_career_list'),
    path('admin/careers/create/', views.CareerCreateView.as_view(), name='career_create'),
    path('admin/careers/<int:pk>/update/', views.CareerUpdateView.as_view(), name='career_update'),
]
