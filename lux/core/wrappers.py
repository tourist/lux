import json

from pulsar.apps.wsgi import (route, wsgi_request, cached_property,
                              html_factory)
from pulsar.apps import wsgi
from pulsar.apps.wsgi import RouterParam, Router, render_error_debug
from pulsar.apps.wsgi.utils import error_messages
from pulsar.utils.httpurl import JSON_CONTENT_TYPES
from pulsar.utils.structures import mapping_iterator

from lux.utils import unique_tuple
from pulsar.utils.exceptions import MethodNotAllowed

__all__ = ['Html', 'WsgiRequest', 'Router', 'HtmlRouter',
           'JsonRouter', 'route', 'wsgi_request',
           'cached_property', 'html_factory', 'RedirectRouter',
           'RouterParam', 'JSON_CONTENT_TYPES',
           'DEFAULT_CONTENT_TYPES']

Html = wsgi.Html


DEFAULT_CONTENT_TYPES = unique_tuple(('text/html', 'text/plain', 'text/csv'),
                                     JSON_CONTENT_TYPES)


class WsgiRequest(wsgi.WsgiRequest):
    '''Extend pulsar :class:`~pulsar.apps.wsgi.wrappers.WsgiRequest` with
    additional methods and attributes.
    '''
    @property
    def app(self):
        '''The :class:`.Application` running the website.'''
        return self.cache.app

    @property
    def config(self):
        '''The :attr:`.Application.config` dictionary'''
        return self.cache.app.config

    @property
    def logger(self):
        '''Shortcut to app logger'''
        return self.cache.app.logger

    @cached_property
    def html_document(self):
        '''The HTML document for this request.'''
        return self.app.html_document(self)

    @cached_property
    def cache_server(self):
        cache = self.config['CACHE_SERVER']
        if isinstance(cache, str):
            raise NotImplementedError
        return cache

    def has_permission(self, action, model):
        '''Check if this request has permission on ``model`` to perform a
        given ``action``'''
        return self.app.permissions.has(self, action, model)


wsgi.set_wsgi_request_class(WsgiRequest)


class RedirectRouter(Router):

    def __init__(self, routefrom, routeto):
        super(RedirectRouter, self).__init__(routefrom, routeto=routeto)

    def get(self, request):
        return request.redirect(self.routeto)


class JsonRouter(Router):
    response_content_types = ['application/json']


class HtmlRouter(Router):
    '''Extend pulsar :class:`~pulsar.apps.wsgi.routers.Router`
    with content management.'''
    in_nav = False
    controller = None
    html_body_template = None
    form = None
    response_content_types = DEFAULT_CONTENT_TYPES

    def get(self, request):
        '''Return the html template used by the GET method
        and content-type is text/html
        '''
        response = request.response
        ct = response.content_type or ''
        if ct.startswith('text/html'):
            app = request.app
            template = self.get_html_body_template(request)
            html = self.get_html(request)
            if isinstance(html, Html):
                html = html.render(request)
            context = {'html_main': html}
            return app.html_response(request, template, context=context)
        elif ct == 'application/json':
            return self.get_json(request)
        else:
            return self.get_text(request)

    def get_html(self, request):
        '''Must be implemented by subclasses
        '''
        return ''

    def get_json(self, request):
        return '{}'

    def get_text(self, request):
        return ''

    def get_html_body_template(self, request):
        cms = request.app.cms
        template = (cms.template(self.full_route.path) or
                    self.html_body_template)
        if not template:
            if self.parent:
                template = self.parent.get_html_body_template(request)
            else:
                template = 'home.html'
        return template

    def make_router(self, rule, **params):
        '''Create a new :class:`.Router` form rule and parameters
        '''
        params.setdefault('cls', HtmlRouter)
        return super().make_router(rule, **params)

    def add_api_urls(self, request, api):
        for r in self.routes:
            if isinstance(r, Router):
                r.add_api_urls(request, api)

    def get_api_info(self, app):
        '''The api name for this :class:`.Router`
        '''


class HeadMeta(object):
    '''Wrapper for HTML5 head metatags.
    '''
    def __init__(self, head):
        self.head = head

    def __repr__(self):
        return repr(self.head.meta.children)

    def __str__(self):
        return str(self.head.meta.children)

    def update(self, iterable):
        for name, value in mapping_iterator(iterable):
            self.set(name, value)

    def __setitem__(self, entry, content):
        self.set(entry, content)

    def __getitem__(self, entry):
        return self.get(entry)

    def __len__(self):
        return len(self.head.meta.children)

    def __iter__(self):
        return iter(self.head.meta.children)

    def set(self, entry, content, meta_key=None):
        '''Set the a meta tag with ``content`` and ``entry`` in the HTML5 head.
        The ``key`` for ``entry`` is either ``name`` or ``property`` depending
        on the value of ``entry``.
        '''
        if content:
            if entry == 'title':
                self.head.title = content
            else:
                self.head.replace_meta(entry, content, meta_key)

    def get(self, entry, meta_key=None):
        if entry == 'title':
            return self.head.title
        else:
            return self.head.get_meta(entry, meta_key=meta_key)


def error_handler(request, exc):
    '''Default renderer for errors.'''
    app = request.app
    response = request.response
    if not response.content_type:
        content_type = request.get('default.content_type')
        if content_type:
            response.content_type = request.content_types.best_match(
                content_type)
    content_type = None
    if response.content_type:
        content_type = response.content_type.split(';')[0]
    is_html = content_type == 'text/html'

    if app.debug:
        msg = render_error_debug(request, exc, is_html)
    else:
        msg = error_messages.get(response.status_code) or str(exc)
        if is_html:
            msg = app.render_template(['%s.html' % response.status_code,
                                       'error.html'],
                                      {'status_code': response.status_code,
                                       'status_message': msg})
    #
    if is_html:
        doc = request.html_document
        doc.head.title = response.status
        doc.body.append(msg)
        return doc.render(request)
    elif content_type in JSON_CONTENT_TYPES:
        return json.dumps({'status': response.status_code,
                           'message': msg})
    else:
        return '\n'.join(msg) if isinstance(msg, (list, tuple)) else msg
