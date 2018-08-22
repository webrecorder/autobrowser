from autobrowser import BaseAutoBrowser, BaseAutoTab
import logging
import json

from cripy.asyncio import Client

import asyncio
import aioredis


# ============================================================================
class Driver(object):
    def __init__(self, loop):
        self.browsers = {}

    async def pubsub_loop(self):
        self.redis = await aioredis.create_redis('redis://redis', loop=loop)

        channels = await self.redis.subscribe('auto-event')

        while channels[0].is_active:
            msg = await channels[0].get(encoding='utf-8')
            msg = json.loads(msg)

            if msg['type'] == 'start':
                self.add_browser(msg['reqid'])

            elif msg['type'] == 'stop':
                self.remove_browser(msg['reqid'])

    def add_browser(self, reqid):
        logging.debug('Start Automating Browser: ' + reqid)
        browser = self.browsers.get(reqid)
        if not browser:
            browser = BaseAutoBrowser(api_host='http://shepherd:9020',
                                      reqid=reqid,
                                      tab_class=BehaviorTab)

            self.browsers[reqid] = browser

    def remove_browser(self, reqid):
        logging.debug('Stop Automating Browser: ' + reqid)
        browser = self.browsers.get(reqid)
        if not browser:
            return

        browser.close()
        del self.browsers[reqid]


# ============================================================================
class BehaviorTab(BaseAutoTab):
    def __init__(self, browser, tab_data, **opts):
        self.browser = browser
        self.tab_data = tab_data
        self.client = None
        self.running = False

        self.behaviors = []
        self.all_behaviors = None

        self.start_async()

    def start_async(self):
        asyncio.ensure_future(self.init_client())

    async def init_client(self):
        self.client = await Client(self.tab_data['webSocketDebuggerUrl'])

        self.client.Inspector.detached(self.devtools_reconnect)

        await self.client.Page.enable()

        if self.running:
            return

        self.running = True

        self.add_behavior(AutoScroll(self))
        self.add_behavior(VideoScrollPauseChecker(self))
        self.all_behaviors = asyncio.gather(*self.behaviors)

    def close(self):
        self.running = False

        if self.all_behaviors:
            self.all_behaviors.cancel()
            self.all_behaviors = None

        if self.client:
            asyncio.ensure_future(self.client.dispose())
            self.client = None

    def add_behavior(self, behavior):
        self.behaviors.append(asyncio.ensure_future(behavior))

    def devtools_reconnect(self, result):
        if result['reason'] == 'replaced_with_devtools':
            self._reconnect = True
            asyncio.ensure_future(self.wait_for_reconnect())

    async def wait_for_reconnect(self):
        while True:
            try:
                await self.init_client()
                break
            except Exception as e:
                print(e)

            await asyncio.sleep(2.0)


# ============================================================================
class Behavior(object):
    def __init__(self, tab):
        self.tab = tab
        self.paused = False

    def __await__(self):
        return self.run().__await__()


# ============================================================================
class AutoScroll(Behavior):
    SCROLL_COND = 'window.scrollY + window.innerHeight < Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)'

    SCROLL_INC = 'window.scrollBy(0, 80)'

    SCROLL_SPEED = 0.2

    async def run(self):
        while True:
            is_paused = await self.tab.client.Runtime.evaluate('window.__wr_scroll_paused')
            self.paused = bool(is_paused['result'].get('value'))

            if self.paused:
                print('Scroll Paused')
                await asyncio.sleep(1.0)
                continue

            should_scroll = await self.tab.client.Runtime.evaluate(self.SCROLL_COND)

            if not should_scroll['result']['value']:
                break

            await self.tab.client.Runtime.evaluate(self.SCROLL_INC)

            await asyncio.sleep(self.SCROLL_SPEED)


# ============================================================================
class VideoScrollPauseChecker(Behavior):
    PAUSE_EVENTS = ['play', 'playing']
    UNPAUSE_EVENTS = ['ended', 'abort', 'pause']

    def debugger_paused(self, result):
        asyncio.ensure_future(self.tab.client.Debugger.resume())

        event_name = result['data']['eventName']
        event_name = event_name.split('listener:', 1)[-1]
        print('Debug Event', event_name)

        if event_name in self.PAUSE_EVENTS:
            print('Pausing Scroll')
            asyncio.ensure_future(self.tab.client.Runtime.evaluate('window.__wr_scroll_paused = true'))

            asyncio.ensure_future(self.tab.client.Runtime.evaluate('document.querySelector("VIDEO").playbackRate = 8.0'))

        elif event_name in self.UNPAUSE_EVENTS:
            print('Unpausing Scroll')
            asyncio.ensure_future(self.tab.client.Runtime.evaluate('window.__wr_scroll_paused = false'))

    async def run(self):
        # listen to events
        await self.tab.client.Debugger.enable()
        self.tab.client.Debugger.paused(self.debugger_paused)

        for name in self.PAUSE_EVENTS:
            await self.tab.client.DOMDebugger.setEventListenerBreakpoint(eventName=name)

        for name in self.UNPAUSE_EVENTS:
            await self.tab.client.DOMDebugger.setEventListenerBreakpoint(eventName=name)


# ============================================================================
loop = asyncio.get_event_loop()


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s: [%(levelname)s]: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.DEBUG)

    driver = Driver(loop)

    loop.run_until_complete(driver.pubsub_loop())


