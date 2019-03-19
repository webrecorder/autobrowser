from abc import ABC, abstractmethod
from asyncio import AbstractEventLoop, Task
from typing import Any, Awaitable, ClassVar, Dict, List, Optional, TYPE_CHECKING, Union

from pyee2 import EventEmitter

from .events import BrowserEvents, TabEvents

if TYPE_CHECKING:
    from autobrowser.automation import AutomationConfig, BrowserExitInfo, TabClosedInfo

__all__ = ["Behavior", "BehaviorManager", "Browser", "Driver", "Tab"]


class Behavior(ABC):
    """A behavior represents a series of actions that are to be performed in the page (tab)
    or specific frame within the page.

    This class defines the expected interface for all behaviors.
    Each behavior has an associated tab and configuration. If a behaviors configuration is not supplied
    then it is an empty dictionary, allowing subclasses to fill in information as necessary.

    Behavior lifecycle:
     - run() -> init(), action loop
     - init() -> pre_action_init
     - action loop -> while(not done): perform_action
    """

    @property
    @abstractmethod
    def done(self) -> bool:
        """Is the behavior done"""

    @property
    @abstractmethod
    def paused(self) -> bool:
        """Is the behavior paused.

        A behavior in the paused state indicates that it has yet to reach its know completion point,
        but is waiting for some condition to occur before resuming.
        """

    @abstractmethod
    def reset(self) -> None:
        """Reset the behavior to its initial state"""

    @abstractmethod
    def end(self) -> None:
        """Unconditionally set the behaviors running state to done"""

    @abstractmethod
    async def init(self) -> None:
        """Initialize the behavior. If the behavior was previously initialized this is a no op"""

    @abstractmethod
    async def pre_action_init(self) -> None:
        """Perform all initialization required to run the behavior.

        Behaviors that require so setup before performing their actions
        should override this method in order to perform the required setup
        """

    @abstractmethod
    async def perform_action(self) -> None:
        """Perform the behaviors action in the page"""

    @abstractmethod
    def evaluate_in_page(self, js_string: str) -> Awaitable[Any]:
        """Evaluate a string of JavaScript inside the page or frame.

        :param js_string: The string of JavaScript to be evaluated
        """

    @abstractmethod
    async def run(self) -> None:
        """Run the behaviors actions.

        Set the tabs running behavior at the start and
        once the behavior is finished (performed all actions)
        unsets the tabs running behavior.

        Behaviors lifecycle represented by invoking this method:
         - init
         - perform action while not done
         - call tab.collect_outlinks if collection outlinks
         after an action was performed
        """

    @abstractmethod
    async def timed_run(self, max_run_time: Union[int, float]) -> None:
        pass

    @abstractmethod
    def run_task(self) -> Task:
        """Run the behavior as a task, if the behavior is already running as
        a task the running behavior run task is returned"""

    @abstractmethod
    def timed_run_task(self, max_run_time: Union[int, float]) -> Task:
        """Run the behavior as a task that will run for maximum amount of time, if the behavior is already running as
        a task the running behavior run task is returned"""

    @abstractmethod
    def _finished(self) -> None:
        """Sets the state of the behavior to done"""

    def __await__(self) -> Any:
        return self.run().__await__()


class BehaviorManager(ABC):
    """This class defines the expected interface for all behavior mangers"""

    @abstractmethod
    async def behavior_for_url(self, url: str, tab: "Tab", **kwargs: Any) -> Behavior:
        """Retrieve the behavior for the supplied URL, if no behavior's
        url matches then a default behavior is returned.

        :param url: The url to receive the Behavior class for
        :param tab: The browser tab the behavior is to run in
        :param kwargs: Additional keyword arguments to be used to instantiation the behavior
        :return: The Behavior for the URL
        """
        pass

    @abstractmethod
    async def behavior_info_for_url(self, url: str) -> Dict:
        """Retrieve the behavior info for the supplied URL.

        :param url: The url to receive the Behavior class for
        :return: The matched Behavior's info
        """
        pass


class Browser(EventEmitter, ABC):
    """A Browser class represents a remote Chrome browser and N tabs"""

    Events: ClassVar[BrowserEvents] = BrowserEvents()

    @property
    @abstractmethod
    def autoid(self) -> str:
        """Retrieve the automation id of the running automation"""

    @property
    @abstractmethod
    def reqid(self) -> str:
        """Retrieve the request id for this process of the running
        automation"""

    @property
    @abstractmethod
    def config(self) -> "AutomationConfig":
        pass

    @property
    @abstractmethod
    def behavior_manager(self) -> BehaviorManager:
        pass

    @property
    @abstractmethod
    def loop(self) -> AbstractEventLoop:
        pass

    @abstractmethod
    async def init(self, tab_datas: Optional[List[Dict]] = None) -> None:
        """Initialize the browser.

        :param tab_datas: List of data about the tabs to be connected to
        """

    @abstractmethod
    async def reinit(self, tab_data: Optional[List[Dict]] = None) -> None:
        """Re initialize the browser, if the browser was previously running
        this is an no-op.

        :param tab_data: List of data about the tabs to be connected to
        """

    @abstractmethod
    async def close(self, gracefully: bool = False) -> None:
        """Initiate the close of the browser either gracefully or forcefully.

        Once all tabs have been closed the `Exiting` event is emitted
        with the browsers exit info.

        :param gracefully: A boolean indicating if we should close the
        tabs gracefully or not.
        """

    @abstractmethod
    async def shutdown_gracefully(self) -> None:
        """Initiate the graceful closing of the browser and its tabs"""

    @abstractmethod
    async def _tab_closed(self, info: "TabClosedInfo") -> None:
        """Listener registered to the Tab Closed event

        :param info: The closed info for the tab that closed
        """


class Driver(ABC):
    """Abstract base driver class that defines a common interface for all
    driver implementations and is responsible for managing the redis connection.

    Drivers have the following lifecycle:
     - await init: initialize all dependant resources
     - await shutdown_condition: all browsers have exited or signal received
     - await shutdown: clean up all initialized resources and return an exit code

    Driver subclasses are expected to not override the run method directly
    but rather override one or more of the following lifecycle methods:
     - init
     - clean_up
     - shutdown
    """

    @abstractmethod
    async def init(self) -> None:
        """Initialize the driver."""

    @abstractmethod
    async def clean_up(self) -> None:
        """Performs any necessary cleanup Close all dependant resources.

        This method should be called from subclasses shutdown.
        """

    @abstractmethod
    async def run(self) -> int:
        """Start running the driver.

        Subclasses should not override this method rather override
        one of the lifecycle methods

        Lifecycle methods called:
          - await init
          - await shutdown_condition
          - await shutdown
        """

    @abstractmethod
    async def gracefully_shutdown_browser(self, browser: Browser) -> None:
        """Gracefully shutdowns a browser and adds its exit info to
        the list of browser exit infos.

        :param browser: The browser to gracefully shutdown
        """

    @abstractmethod
    def determine_exit_code(self) -> int:
        """Determines the exit code based on the exit info's of the browsers.

        If the shutdown condition was met by signal the return value is 1.

        If there were no browser exit info's the return value is 0.

        If there was one browser exit info then the return value is
        the results of calling `BrowserExitInfo.exit_reason_code()`

        Otherwise the return value is `BrowserExitInfo.exit_reason_code()`
        that was seen the most times.

        :return: An exit code based on the exit info's of the browsers
        """

    @abstractmethod
    def initiate_shutdown(self) -> None:
        """Initiate the complete shutdown of the driver (running automation).

        This method should be used to shutdown (stop) the driver from running
        rather than calling :func:`~basedriver.Driver.shutdown` directly
        """

    @abstractmethod
    async def shutdown(self) -> int:
        """Stop the driver from running and perform
        any necessary cleanup required before exiting

        :return: The exit code determined by `determine_exit_code`
        """
        pass

    @abstractmethod
    def on_browser_exit(self, info: "BrowserExitInfo") -> None:
        """Method used as the listener for when a browser
        exits abnormally

        :param info: BrowserExitInfo about the browser
        that exited
        """
        pass


class Tab(EventEmitter, ABC):
    """This class defines the expected interface for all Tab classes"""

    Events: ClassVar[TabEvents] = TabEvents()

    @property
    @abstractmethod
    def loop(self) -> AbstractEventLoop:
        pass

    @property
    @abstractmethod
    def behavior_manager(self) -> BehaviorManager:
        pass

    @property
    @abstractmethod
    def config(self) -> "AutomationConfig":
        pass

    @property
    @abstractmethod
    def connection_closed(self) -> bool:
        pass

    @property
    @abstractmethod
    def autoid(self) -> str:
        """Retrieve the automation id of the running automation"""

    @property
    @abstractmethod
    def reqid(self) -> str:
        """Retrieve the request id for this process of the running
        automation"""

    @property
    @abstractmethod
    def behaviors_paused(self) -> bool:
        """Are the behaviors paused"""

    @property
    @abstractmethod
    def tab_id(self) -> str:
        """Returns the id of the tab this class is controlling"""

    @property
    @abstractmethod
    def tab_url(self) -> str:
        """Returns the URL of the tab this class is controlling"""

    @property
    @abstractmethod
    def running(self) -> bool:
        """Is this tab running (active client connection)"""

    @property
    @abstractmethod
    def reconnecting(self) -> bool:
        """Is this tab attempting to reconnect to the tab"""

    @abstractmethod
    def set_running_behavior(self, behavior: Behavior) -> None:
        """Set the tabs running behavior (done automatically by
        behaviors)

        :param behavior: The behavior that is currently running
        """

    @abstractmethod
    def unset_running_behavior(self, behavior: Behavior) -> None:
        """Un-sets the tabs running behavior (done automatically by
        behaviors)

        :param behavior: The behavior that was running
        """

    @abstractmethod
    def wait_for_net_idle(
        self, num_inflight: int = 2, idle_time: int = 2, global_wait: int = 60
    ) -> Awaitable[None]:
        """Returns a future that  resolves once network idle occurs.

        See the options of autobrowser.util.netidle.monitor for a complete
        description of the available arguments
        """

    @abstractmethod
    async def pause_behaviors(self) -> None:
        """Sets the behaviors paused flag to true"""

    @abstractmethod
    async def resume_behaviors(self) -> None:
        """Sets the behaviors paused flag to false"""

    @abstractmethod
    async def evaluate_in_page(
        self, js_string: str, contextId: Optional[Any] = None
    ) -> Any:
        """Evaluates the supplied string of JavaScript in the tab

        :param js_string: The string of JavaScript to be evaluated
        :return: The results of the evaluation if any
        """

    @abstractmethod
    async def goto(self, url: str, *args: Any, **kwargs: Any) -> Any:
        """Initiates browser navigation to the supplied url.

        See cripy.protocol.Page for more information about additional
        arguments or https://chromedevtools.github.io/devtools-protocol/tot/Page#method-navigate

        :param url: The URL to be navigated to
        :param kwargs: Additional arguments to Page.navigate
        :return: The information returned by Page.navigate
        """

    @abstractmethod
    async def connect_to_tab(self) -> None:
        """Initializes the connection to the remote browser tab and
        sets up listeners for when the connection is closed/detached or the
        browser tab crashes
        """

    @abstractmethod
    async def init(self) -> None:
        """Initialize the client connection to the tab.

        Subclasses are expected to call this method from their
        implementation. This can be the only call in their
        implementation.
        """

    @abstractmethod
    async def close(self) -> None:
        """Close the client connection to the tab.

        Subclasses are expected to call this method from their
        implementation. This can be the only call in their
        implementation.
        """

    @abstractmethod
    async def shutdown_gracefully(self) -> None:
        """Initiates the graceful shutdown of the tab"""

    @abstractmethod
    async def capture_screenshot(self) -> bytes:
        """Capture a screenshot (in png format) of the current page.
        :return: The captured screenshot as bytes
        """

    @abstractmethod
    async def capture_and_upload_screenshot(self) -> None:
        """Capture a screenshot (in png format) of the current page
        and sends the captured screenshot to the configured endpoint
        """

    @classmethod
    @abstractmethod
    def create(cls, *args: Any, **kwargs: Any) -> "Tab":
        """Abstract method for creating new instances of a tab.

        Subclasses are expected to supply the means for creating
        themselves their implementation
        """

    async def collect_outlinks(self) -> None:
        """Collect outlinks from the remote tab somehow.

        Only tabs that require the extraction of outlinks should override
        (provide implementation) for this method.
        """
        pass
