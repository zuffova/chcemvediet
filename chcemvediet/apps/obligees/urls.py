# vim: expandtab
from django.conf.urls import patterns, url

import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^autocomplete/$', views.autocomplete, name='autocomplete'),
)

