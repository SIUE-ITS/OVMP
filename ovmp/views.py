from revproxy.views import ProxyView
from revproxy.response import get_django_response
from django.utils.decorators import method_decorator
from django.conf import settings
from actions import decorators


@method_decorator(decorators.owner_vm, name="dispatch")
class ConsoleProxyView(ProxyView):

    upstream = settings.CONSOLE_UPSTREAM

    def dispatch(self, request, **kwargs):
        path = kwargs['path'].replace("_auto", "")
        self.request_headers = self.get_request_headers()

        redirect_to = self._format_path_to_redirect(request)
        if redirect_to:
            return redirect(redirect_to)

        proxy_response = self._created_proxy_response(request, path)

        self._replace_host_on_redirect_location(request, proxy_response)
        self._set_content_type(request, proxy_response)

        response = get_django_response(proxy_response,
                                       strict_cookies=self.strict_cookies)

        self.log.debug("RESPONSE RETURNED: %s", response)
        return response
