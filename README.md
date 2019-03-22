autobrowser
=====================================
Webrecorder's web browser automation framework

### Configuration

Configuration of autobrowser is done primarily through the environment variables listed below.

Their values are read by the application in [autobrowser/automation/details.py](https://github.com/webrecorder/autobrowser/blob/master/autobrowser/automation/details.py)

**Note**: boolean values (flag/switches) have the following format
 - true: `1`, `true`, `yes`, `y`, `ok`, `on`
 - false: `0`, `false`, `no`, `n`, `nok`, `off`, `env var does not exist`


#### General

REDIS_URL 
 - The URL to be used when connecting to redis (string)
 - Defaults to `redis://localhost`

CHROME_OPTS
 - A string of json used by `LocalDriver` to launch a browser  (string)

CDP_PORT
 - The port to be used when communicating with a browser via the CDP (number)
 - Defaults to `9222`

AUTO_ID **Required when crawling**
 - The id of the entire automation (string)

REQ_ID **Required**
 - The id of the request used to start this part of the entire automation (string)

#### Shepherd

SHEPARD_HOST 
 - The URL that shepard is listening on (string)
 - Defaults to `http://shepherd:9020`
 
BROWSER_ID
 - The id of the browser to be used when requesting one from shepherd (string)
 - Defaults to `chrome:67`

BROWSER_HOST
 - The host name of the browser running in a container (string)
 
REQ_BROWSER_PATH
 - The path to the shepherd endpoint for requesting browsers (string) 
 - Defaults to `/request_browser/`

INIT_BROWSER_PATH
 - The path to the shepherd endpoint for initializing new browsers (string)
 - Defaults to `/init_browser?reqid=`
 
GET_BROWSER_INFO_PATH
 - The path to the shepherd endpoint for requesting information about a browsers (string)
 - Defaults to `/info/`
 
#### Crawling

CRAWL_NO_NETCACHE
 - Should the browsers network cache be disable (bool)
 - Defaults to `true`

NAV_TO 
 - How long should the navigation timeout be (time value in seconds)
 - Defaults to `30`

WAIT_FOR_Q 
 - How long should the crawler tab wait for the frontier q to become populated (number)
 - Defaults to `60`

BEHAVIOR_RUN_TIME 
 - How long should the behaviors be allowed to run for (time value in seconds)
 - Defaults to `60`

NUM_TABS 
 - How many tabs should the be created per browser connected to (number)
 - Defaults to `1`

TAB_TYPE 
 - Which tab type should be used (BehaviorTab or CrawlerTab)
 - Defaults to `BehaviorTab`

#### Behaviors

BEHAVIOR_API_URL
 - The base URL to be used for interaction with the behaviors api (string)
 - Defaults to `http://localhost:3030` 

FETCH_BEHAVIOR_ENDPOINT 
 - The URL of the behaviors api endpoint for retrieving just the behaviors JavaScript (string)
 - Defaults to `{BEHAVIOR_API_URL}/behavior?url=` 

FETCH_BEHAVIOR_INFO_ENDPOINT 
 - The URL of the behaviors api endpoint for retrieving just the behaviors info (string)
 - Defaults to `{BEHAVIOR_API_URL}/info?url=` 

SCREENSHOT_API_URL
 - The url to be used to send screenshots of the page after a behavior has run (string)
 - **Note** acts as a flag indicating screenshots are to be taken

SCREENSHOT_TARGET_URI **Required if SCREENSHOT_API_URL is provided**
 - The url for the resource record for the screenshots (string)

SCREENSHOT_FORMAT
 - The type of screenshot to be taken `png` or `jpg` (string)
 - Defaults to `png`

#### Javascript expressions
 
BEHAVIOR_ACTION_EXPRESSION
 - The expression used to initiate the next action of a behavior (string)
 - Defaults to: `window.$WRIteratorHandler$()`
 
BEHAVIOR_PAUSED_EXPRESSION
 - The expression used to determine if the running behavior is in the paused state (string)
 - Defaults to: `window.$WBBehaviorPaused === true`

PAGE_URL_EXPRESSION
 - The expression used to determine the URL of the page (string)
 - Defaults to: `window.location.href`

OUTLINKS_EXPRESSION
 - The expression used to retrieve the outlinks collected by the running behavior (string)
 - Defaults to: `window.$wbOutlinks$`
 
CLEAR_OUTLINKS_EXPRESSION
 - The expression used to clear the outlinks collected by the running behavior (string)
 - Defaults to: `window.$wbOutlinkSet$.clear()`
 
NO_OUT_LINKS_EXPRESS
 - The expression used to indicate to the behavior that it is not to collect outlinks (string)
 - Defaults to: `window.$WBNOOUTLINKS = true`
