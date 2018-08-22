from gevent import monkey; monkey.patch_all()
from bottle import route, request, default_app, jinja2_view, debug, static_file
from gevent.pywsgi import WSGIServer
import redis


# ============================================================================
class Server(object):
    def __init__(self):
        self.application = default_app()

        debug(True)

        self.init_routes()

        self.redis = redis.StrictRedis(host='redis')

    def init_routes(self):
        @route('/view/<url:path>')
        @jinja2_view('autobrowser.html', template_lookup=['templates'])
        def view(url):
            return {'url': url,
                    'browser': 'chrome:67'
                   }

        @route('/static/<filepath:path>')
        def server_static(filepath):
            return static_file(filepath, root='./static/')

        @route('/api/auto/<reqid>')
        def trigger_auto(reqid):
            self.redis.publish('auto-start', reqid)
            return {}


# ============================================================================
#application = Main().application
#run(host='0.0.0.0', port='9021', server='gevent')
wh = WSGIServer(('0.0.0.0', 9021), Server().application)
wh.serve_forever()



