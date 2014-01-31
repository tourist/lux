import json
import time

from pulsar import HttpException
from pulsar.apps import ws


__all__ = ['CrudWebSocket']


class CrudWebSocket(ws.WS):
    '''A websocket handler for CRUD operations
    '''
    def on_open(self, websocket):
        websocket.handshake.cache.started = time.time()

    def on_message(self, websocket, message):
        '''Handle an incoming text message which is JSON encoded.

        The decoded message is a dictionary containing the following entries:

        * ``action``, the action to perform on the data included in
          the message.
          The action must be implemented as a method of this class.
          Available out of the box are the CRUD actions :meth:`get`,
          :meth:`post`, :meth:`put` and :meth:`delete`.
        * ``mid``, the message unique identifier.
        '''
        message = json.loads(message)
        mid = message.get('mid')
        action = message.get('action', '').lower().replace('-', '_')
        handle = getattr(self, action, None) if action else None
        if not handle:
            if action:
                self.error(websocket, message, 'Unknown "%s" action.'
                           % message['action'])
            else:
                self.error(websocket, mid, 'Message action not available')
        else:
            return handle(websocket, message)

    ########################################################################
    ##    HANDLERS
    def get(self, websocket, message):
        '''Handle get response. Requires a model.'''
        manager = self.manager(websocket, message)
        if manager:
            pks = message.get('data')
            if pks:
                query = manager.filter(**{manager._meta.pkname(): pks})
                instances = yield query.all()
                self.write_instances(websocket, message, instances)

    def post(self, websocket, message):
        '''Handle get response. Requires a model.'''
        manager = self.manager(websocket, message)
        if manager:
            create = self.update_create
            if websocket.handshake.has_permission('create', manager):
                data_list = message.get('data')
                with manager.session().begin() as t:
                    for data in data_list:
                        instance = create(websocket, manager, data['fields'])
                        instance._cid = data['id']
                        t.add(instance)
                yield t.on_result
                self.write_instances(websocket, message, t.saved[manager])
            else:
                self.error(websocket, message, 'Permission denied')

    def put(self, websocket, message):
        '''Handle put response. Requires a model.'''
        manager = self.manager(websocket, message)
        if manager:
            update = self.update_create
            pkname = manager._meta.pkname()
            data = message['data']
            pks = {}
            pks = dict(((d['id'], d.get('fields')) for d in data if 'id' in d))
            if pks:
                instances = yield manager.filter(**{pkname: tuple(pks)}).all()
                with manager.session().begin() as t:
                    for instance in instances:
                        if websocket.handshake.has_permission('update',
                                                              instance):
                            instance._cid = instance.pkvalue()
                            t.add(update(websocket, manager,
                                         pks[instance._cid], instance))
                yield t.on_result
                saved = t.saved[manager]
            else:
                saved = []
            self.write_instances(websocket, message, saved)

    def delete(self, websocket, message):
        '''Handle get response. Requires a model.'''
        manager = self.manager(websocket, message)
        if manager:
            pass

    def status(self, websocket, message):
        started = websocket.handshake.cache.started
        if not started:
            websocket.handshake.cache.started = started = time.time()
        message['data'] = {'uptime': time.time() - started}
        self.write(websocket, message)

    ########################################################################
    ##    INTERNALS
    def write(self, websocket, message):
        websocket.write(json.dumps(message))

    def manager(self, websocket, message):
        '''Get the manager for a :ref:`CRUD message <crud-message>`.'''
        model = message.get('model')
        if not model:
            self.error(websocket, message, 'Model type not available')
        else:
            manager = getattr(websocket.handshake.models, model, None)
            if not manager:
                self.error(websocket, message, 'Unknown model %s' % model)
            else:
                return manager

    def update_create(self, websocket, manager, fields, instance=None):
        '''Internal method invoked by both the :meth:`post` and and :meth:`put`
method, respectively when creating and updating an ``instance`` of a model.

:parameter websocket: the websocket serving the request.
:parameter manager: the model manager.
:parameter fields: model fields used to create or update the ``instance``.
:parameter instance: Optional instance of the ``manager`` model
    (when updating).
:return: a new or an updated ``instance``
'''
        if instance is None:
            return manager(**fields)
        else:
            for name in fields:
                instance.set(name, fields[name])
            return instance

    def write_instances(self, websocket, message, instances):
        if instances:
            instances = [{'fields': i.tojson(),
                          'id': getattr(i, '_cid', i.pkvalue())}
                         for i in instances]
        message['data'] = instances
        self.write(websocket, message)

    def error(self, websocket, message, msg):
        '''Handle an error in response'''
        websocket.handshake.app.logger.warning(msg)
        message['error'] = msg
        message.pop('data', None)
        self.write(websocket, message)
