"""A modified asyncio.runners.run that ensures the process exits with a specific exit code"""
import asyncio
import logging
import uvloop
import sys
from asyncio import coroutines, events, tasks
from typing import Coroutine

__all__ = ["run_automation"]

logger = logging.getLogger("autobrowser")

if not isinstance(asyncio.get_event_loop_policy(), uvloop.EventLoopPolicy):
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


def run_automation(main: Coroutine, *, debug: bool = False) -> None:
    logger.info("run_automation: Running automation")
    sys.exit(_run(main, debug=debug))


def _run(main: Coroutine, *, debug: bool = False):
    if events._get_running_loop() is not None:
        raise RuntimeError(
            "run_automation() cannot be called from a running event loop"
        )

    if not coroutines.iscoroutine(main):
        raise ValueError("a coroutine was expected, got {!r}".format(main))
    loop = asyncio.get_event_loop()
    try:
        loop.set_debug(debug)
        result = loop.run_until_complete(main)
        logger.info(f"run_automation: exiting with code {result}")
        return result
    except Exception as e:
        logger.exception(
            "run_automation: While running an automation an exception was thrown",
            exc_info=e,
        )
        return 2
    except KeyboardInterrupt as e:
        logger.exception(
            "run_automation: While running an automation an KeyboardInterrupt happened",
            exc_info=e,
        )
        return 0
    finally:
        try:
            _cancel_all_tasks(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        finally:
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
                    "message": "unhandled exception during run_automation() shutdown",
                    "exception": task.exception(),
                    "task": task,
                }
            )
