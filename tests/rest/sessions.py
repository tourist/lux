from pulsar.apps.test import test_timeout
from pulsar.apps.wsgi import WsgiHandler

import lux
from lux.utils import test


class TestCase(test.TestCase):
    config_file = 'tests.rest'

    def test_app(self):
        from pulsar.apps.greenio import WsgiGreen
        app = self.application()
        handle = app.handler
        self.assertIsInstance(handle, WsgiHandler)
        self.assertEqual(len(handle.middleware), 2)
        handle = app.handler.middleware[1]
        self.assertEqual(handle.pool, None)
        mapper = app.mapper()
        self.assertEqual(len(mapper), 4)

    @test_timeout(30)
    def test_command_create_superuser(self):
        app = self.application()
        yield from self.run_command(app, 'create_databases')
        yield from self.run_command(app, 'create_tables')
        yield from self.run_command(app, 'create_superuser',
                                    ['--username', 'pippo',
                                     '--password', 'pluto'])
        user = yield from app.mapper().user.get(username='pippo')
        self.assertEqual(user.username, 'pippo')
        self.assertTrue(user.is_active())
        self.assertTrue(user.is_superuser())
