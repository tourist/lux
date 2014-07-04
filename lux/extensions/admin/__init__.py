'''Admin interface for a site.

This extension requires the :mod:`~lux.extensions.sessions` extension.
'''
import lux
from lux import Parameter, Html

from pulsar import ImproperlyConfigured, Http404
from .ui import add_css, collapse_width


class Extension(lux.Extension):
    _config = [
        Parameter('ADMIN_URL', 'admin/',
                  'the base url for the admin site'),
        Parameter('ADMIN_THEME', 'default',
                  'Theme for the admin site')
    ]

    def middleware(self, app):
        if not app.auth_backend:
            raise ImproperlyConfigured('sessions backend required')
        path = app.config['ADMIN_URL']
        app.admin = Router(path, name='admin',
                           response_wrapper=require_superuser)
        return [app.admin]


class Router(lux.Router):
    '''A specialised Router for the admin site
    '''
    in_nav = True
    target = None

    def sitemap(self, path):
        '''Build the sitemap for this router.
        '''
        root = self.root
        parent = {'href': root.path(),
                  'name': root.name,
                  'target': '_self'}
        sitemap, page = _sitemap(root, [parent], path, children=True)
        page = parent if path == parent['href'] else page
        return sitemap, page

    def get(self, request):
        path = request.path
        sitemap, page = self.sitemap(path)
        if self.root.path() == path and sitemap:
            return request.redirect(sitemap[0]['href'])
        else:
            ctx = {'sitemap': sitemap,
                   'page': page,
                   'collapse_width': collapse_width,
                   'theme': request.config['ADMIN_THEME']}
            return self.html_response(request, ctx)


    def html_response(self, request, ctx):
        '''Build the html response
        '''
        app = request.app
        context = {'page_footer': app.template('footer.html')}
        return app.html_response(request, 'admin.html', jscontext=ctx,
                                 context=context, title='%s - Admin')

    def wrap_html(self, request, html, span=12):
        '''Default wrapper for html loaded via angular
        '''
        return Html('div',
                    Html('div', html, cn='col-sm-%d' % span),
                    cn='row').render(request)


def _sitemap(self, parents, path, children=False):
    links = []
    page = None
    for route in self.routes:
        # In navigation
        if getattr(route, 'in_nav', False):
            href = route.path()
            link = {'href': href,
                    'name': route.name,
                    'title': getattr(route, 'title', route.name),
                    'parents': parents,
                    'target': getattr(route, 'target', None)}
            if href == path:
                page = link
                parents[-1]['active'] = True
            if children:
                nparents = [link]
                nparents.extend(parents)
                nparents = list(reversed(nparents))
                children, pg = _sitemap(route, nparents, path)
                page = page or pg
            if children:
                parent = {'links': children}
                parent.update(link)
                links.append(parent)
            else:
                links.append(link)
    return links, page


def require_superuser(handler, request):
    user = request.cache.user
    super_user = getattr(user, 'is_superuser', False)
    if hasattr(super_user, '__call__'):
        super_user = super_user()
    if not super_user:
        raise Http404
    return handler(request)