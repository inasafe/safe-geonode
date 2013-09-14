from django.conf.urls.defaults import patterns, url
from django.views.generic import TemplateView

urlpatterns = patterns('',
                       url(r'^$',
                           TemplateView.as_view(template_name="safe/safe.html"),
                           name='calculator'))

urlpatterns += patterns('safe_geonode.views',
                       url(r'^api/v1/calculate/$', 'calculate', name='safe-calculate'),
                       url(r'^api/v1/questions/$', 'questions', name='safe-questions'),
                       url(r'^api/v1/debug/$', 'debug', name='safe-debug'),
)
