from django.conf import settings
from django.core.cache import cache
from django.conf.urls import url
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils.translation import ugettext as _, gettext_lazy


class AdminLockingMixin(object):
    def get_admin_locking_username(self, obj):
        cache_key = 'admin-locking-%s-%s-%s' % (self.model._meta.app_label, self.model._meta.model_name, obj.pk)
        user_id = cache.get(cache_key)
        if user_id:
            return get_user_model().objects.get(pk=int(user_id)).username
        return ''
    get_admin_locking_username.short_description = gettext_lazy('Locked by')
    
    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if obj:
            context['admin_locking_username'] = self.get_admin_locking_username(obj)
        return super().render_change_form(request, context, add=add, change=change, form_url=form_url, obj=obj)

    def locking(self, request, object_id):
        lock_url = request.POST.get('url')
        if not lock_url or not request.user.is_authenticated:
            return JsonResponse({}, status=400)

        lock_timeout = getattr(settings, 'ADMIN_LOCKING_TIMEOUT', 15)
        cache_key = 'admin-locking-%s-%s-%s' % (
            self.model._meta.app_label, self.model._meta.model_name, object_id)
        locking = cache.get(cache_key)
        if locking:
            if int(locking) != request.user.id:
                # page is locked, return data of locker
                user = get_user_model().objects.get(id=int(locking))
                return JsonResponse({
                    'lock_timeout': lock_timeout,
                    'status': 'locked',
                    'message': _(
                        "This page is currently being edited by %(name_and_email)s. "
                        "Please wait for the lock to be lifted.") % {
                            'name_and_email': '%s %s &lt;<a href="mailto:%s">%s</a>&gt;' % (
                                user.first_name, user.last_name, user.email, user.email),
                        },
                })

            if request.POST.get('action') == 'clear':
                # locked by requestor who wants it cleared - do so
                cache.delete(cache_key)
                return JsonResponse({}, status=204)

        cache.set(cache_key, request.user.id, lock_timeout)

        return JsonResponse({
            'status': 'locking',
            'lock_timeout': lock_timeout,
            'message': _("Page lock has been lifted!"),
            'link_message': _("Click here to edit"),
        })

    def get_urls(self):
        return [
            url(r'^(.+)/locking/$', self.admin_site.admin_view(self.locking)),
        ] + super().get_urls()

    class Media:
        js = ('admin/js/jquery.init.js', 'admin_locking/admin_locking.js',)
