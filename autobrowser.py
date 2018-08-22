import time
import requests
import logging

logger = logging.getLogger('autobrowser')


# ============================================================================
class BaseAutoBrowser(object):
    CDP_JSON = 'http://{ip}:9222/json'
    CDP_JSON_NEW = 'http://{ip}:9222/json/new'

    REQ_BROWSER_URL = '/request_browser/{browser}'
    INIT_BROWSER_URL = '/init_browser?reqid={reqid}'
    GET_BROWSER_INFO_URL = '/info/{reqid}'

    WAIT_TIME = 0.5

    def __init__(self, api_host, browser_id='chrome:60',
                 reqid=None, cdata=None, num_tabs=1,
                 pubsub=False, tab_class=None, tab_opts=None):

        self.api_host = api_host

        self.browser_id = browser_id

        self.cdata = cdata

        self.reqid = reqid
        self.ip = None

        self.num_tabs = num_tabs

        self.tab_class = tab_class or BaseAutoTab
        self.tab_opts = tab_opts or {}

        self.running = False

        self.init(self.reqid)

        logger.debug('Auto Browser Inited: ' + self.reqid)

    def listener(self, *args, **kwargs):
        pass

    def reinit(self):
        if self.running:
            return

        self.init()

        logger.debug('Auto Browser Re-Inited: ' + self.reqid)

    def get_ip_for_reqid(self, reqid):
        try:
            res = requests.get(self.api_host + self.GET_BROWSER_INFO_URL.format(reqid=reqid))

            return res.json().get('ip')
        except:
            return None

    def init(self, reqid=None):
        self.tabs = []
        ip = None
        tab_datas = None

        self.close()

        # attempt to connect to existing browser/tab
        if reqid:
            #ip = self.browser_mgr.get_ip_for_reqid(reqid)
            ip = self.get_ip_for_reqid(reqid)
            if ip:
                tab_datas = self.find_browser_tabs(ip)

            # ensure reqid is removed
            if not tab_datas:
                self.listener('browser_removed', reqid)

        # no tab found, init new browser
        if not tab_datas:
            reqid, ip, tab_datas = self.init_new_browser()

        self.reqid = reqid
        self.ip = ip
        self.tabs = []

        for tab_data in tab_datas:
            tab = self.tab_class(self, tab_data, **self.tab_opts)
            self.tabs.append(tab)

        self.listener('browser_added', reqid)

    def find_browser_tabs(self, ip, url=None, require_ws=True):
        try:
            res = requests.get(self.CDP_JSON.format(ip=ip))
            tabs = res.json()
        except Exception as e:
            logging.debug(str(e))
            return {}

        filtered_tabs = []

        for tab in tabs:
            logger.debug('Tab: ' + str(tab))

            if require_ws and 'webSocketDebuggerUrl' not in tab:
                continue

            if tab.get('type') == 'page' and (not url or url == tab['url']):
                filtered_tabs.append(tab)

        return filtered_tabs

    def get_tab_for_url(self, url):
        tabs = self.find_browser_tabs(self.ip, url=url, require_ws=False)
        if not tabs:
            return None

        id_ = tabs[0]['id']
        for tab in self.tabs:
            if tab.tab_id == id_:
                return tab

        return None

    def add_browser_tab(self, ip):
        try:
            res = requests.get(self.CDP_JSON_NEW.format(ip=ip))
            tab = res.json()
        except Exception as e:
            logger.error('*** ' + str(e))

        return tab

    def stage_new_browser(self, browser_id, data):
        try:
            req_url = self.REQ_BROWSER_URL.format(browser=browser_id)
            res = requests.post(self.api_host + req_url, data=data)

        except Exception as e:
            logger.debug(str(e))
            return {'error': 'not_available'}

        reqid = res.json().get('reqid')

        if not reqid:
            return {'error': 'not_inited',
                    'browser_id': browser_id}

        return reqid

    def init_new_browser(self):
        reqid = self.stage_new_browser(self.browser_id, self.cdata)

        # wait for browser init
        while True:
            res = requests.get(self.api_host + self.INIT_BROWSER_URL.format(reqid=reqid))

            try:
                res = res.json()
            except Exception as e:
                logger.debug('Browser Init Failed: ' + str(e))
                return None, None, None

            if 'cmd_port' in res:
                break

            #if reqid not in self.req_cache:
            #    logger.debug('Waited too long, cancel browser launch')
            #    return False

            logger.debug('Waiting for Browser: ' + str(res))
            time.sleep(self.WAIT_TIME)

        logger.debug('Launched: ' + str(res))

        self.running = True

        # wait to find first tab
        while True:
            tab_datas = self.find_browser_tabs(res['ip'])
            if tab_datas:
                logger.debug(str(tab_datas))
                break

            time.sleep(self.WAIT_TIME)
            logger.debug('Waiting for first tab')

        # add other tabs
        for tab_count in range(self.num_tabs - 1):
            tab_data = self.add_browser_tab(res['ip'])
            tab_datas.append(tab_data)

        return reqid, res['ip'], tab_datas

    def close(self):
        self.running = False

        if self.reqid:
            self.listener('browser_removed', self.reqid)

        for tab in self.tabs:
            tab.close()

        self.reqid = None


# ============================================================================
class BaseAutoTab(object):
    def __init__(self, **opts):
        pass

    def close(self):
        pass


# ============================================================================
class CallRDP(object):
    def __init__(self, func, method=''):
        self.func = func
        self.method = method

    def __getattr__(self, name):
        return CallRDP(self.func, self.method + '.' + name if self.method else name)

    def __call__(self, **kwargs):
        callback = kwargs.pop('callback', None)
        self.func({"method": self.method,
                   "params": kwargs}, callback=callback)


