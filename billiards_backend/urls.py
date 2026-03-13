from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # 原include('user_app.urls') → include('users.urls')
    path('api/user/', include('users.urls')),
    path('api/match/', include('match.urls')),
]