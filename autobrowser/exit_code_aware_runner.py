from asyncio import coroutines, events, tasks
from typing import Coroutine
import sys
import logging

__all__ = ["run_automation"]

logger = logging.getLogger("autobrowser")


def run_automation(main: Coroutine, *, debug: bool = False) -> None:
    logger.info('run_automation: Running automation')
    sys.exit(_run(main, debug=debug))


def _run(main: Coroutine, *, debug: bool = False):
    if events._get_running_loop() is not None:
        raise RuntimeError("start() cannot be called from a running event loop")

    if not coroutines.iscoroutine(main):
        raise ValueError("a coroutine was expected, got {!r}".format(main))
    loop = events.new_event_loop()
    try:
        events.set_event_loop(loop)
        loop.set_debug(debug)
        return loop.run_until_complete(main)
    except Exception as e:
        logger.exception('run_automation: While running an automation an exception was thrown', exc_info=e)
        return 2
    except KeyboardInterrupt as e:
        logger.exception('run_automation: While running an automation an KeyboardInterrupt happened', exc_info=e)
        return 0
    finally:
        try:
            _cancel_all_tasks(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            events.set_event_loop(None)
            loop.close()


def _cancel_all_tasks(loop):
    to_cancel = tasks.all_tasks(loop)
    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    loop.run_until_complete(tasks.gather(*to_cancel, loop=loop, return_exceptions=True))

    for task in to_cancel:
        if task.cancelled():
            continue
        if task.exception() is not None:
            loop.call_exception_handler(
                {
                    "message": "unhandled exception during asyncio.run() shutdown",
                    "exception": task.exception(),
                    "task": task,
                }
            )
